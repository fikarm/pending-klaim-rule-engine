#!/usr/bin/env python3
"""Kerangka engine evaluasi aturan pending klaim.

Alur: claim_facts (JSON) + rules (JSON) -> hasil per aturan (PASS/FAIL/REVIEW/NOT_APPLICABLE)
beserta jejak bukti (trace) untuk audit.

Prinsip:
- Deterministik: tidak ada LLM di sini. LLM hanya mengisi fakta (lihat claim_facts_schema.json).
- Logika tiga nilai (True / False / None=tidak diketahui). Data yang kurang tidak dianggap
  salah, kecuali aturan menyatakan on_missing="fail".
- Tanpa dependensi eksternal (hanya pustaka standar Python 3.9+).

Pakai:
    python klaim_engine.py evaluate --rules rules_ba_2019.json --facts claim_facts_example.json
    python klaim_engine.py lint --rules rules_ba_2019.json --catalog field_catalog.json
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

# --------------------------------------------------------------------------------------
# Logika tiga nilai (Kleene): True, False, None (tidak diketahui)
# --------------------------------------------------------------------------------------
T, F, U = True, False, None
TRI_LABEL = {True: "T", False: "F", None: "U"}


def tri_all(vals: list) -> Optional[bool]:
    if any(v is F for v in vals):
        return F
    if all(v is T for v in vals):
        return T
    return U


def tri_any(vals: list) -> Optional[bool]:
    if any(v is T for v in vals):
        return T
    if all(v is F for v in vals):
        return F
    return U


def tri_not(v: Optional[bool]) -> Optional[bool]:
    return U if v is U else (not v)


def tri_at_least(n: int, vals: list) -> Optional[bool]:
    t = sum(1 for v in vals if v is T)
    u = sum(1 for v in vals if v is U)
    if t >= n:
        return T
    if t + u < n:
        return F
    return U


# --------------------------------------------------------------------------------------
# Opsi
# --------------------------------------------------------------------------------------
@dataclass
class Options:
    # Status di luar daftar tetap ditampilkan sebagai REVIEW bila trigger cocok.
    include_statuses: tuple = ("active",)
    # Fakta hasil LLM di bawah ambang ini diabaikan dan hasilnya jadi REVIEW.
    min_confidence: float = 0.7
    # Bila dokumen wajib belum ada padahal kriteria terpenuhi: "review" atau "fail".
    # KEPUTUSAN KEBIJAKAN: sesuaikan dengan praktik verifikator Anda.
    missing_document_policy: str = "review"
    # Parameter turunan. None = jangan membuat fakta turunan (tidak menebak ambang).
    derivation: dict = field(
        default_factory=lambda: {"leukosit_tinggi_threshold": None}
    )


# --------------------------------------------------------------------------------------
# Utilitas kode ICD
# --------------------------------------------------------------------------------------
def code_matches(code: str, pattern: str) -> bool:
    """Cocokkan kode dengan pola wildcard. 'I50.*' juga cocok dengan 'I50'."""
    code, pattern = code.upper(), pattern.upper()
    if pattern.endswith(".*") and code == pattern[:-2]:
        return True
    return fnmatch.fnmatchcase(code, pattern)


# --------------------------------------------------------------------------------------
# Konteks: akses fakta (header klaim diperlakukan sebagai fakta semu)
# --------------------------------------------------------------------------------------
class Context:
    def __init__(
        self, doc: dict, opts: Options, rule_lineage: Optional[dict] = None
    ):
        self.doc = doc
        self.claim = doc["claim"]
        self.facts = doc.get("facts", [])
        self.opts = opts
        self.rule_lineage = copy.deepcopy(rule_lineage or {})

    def _header_facts(self, fld: str) -> Optional[list]:
        c = self.claim
        if fld == "claim.diagnoses":
            value, kind, unit = (
                [d["code"] for d in c.get("diagnoses", [])],
                "category_list",
                None,
            )
        elif fld == "claim.procedures":
            value, kind, unit = (
                [p["code"] for p in c.get("procedures", [])],
                "category_list",
                None,
            )
        elif fld == "claim.encounter_type":
            value, kind, unit = c.get("encounter_type"), "category", None
        elif fld == "patient.age_days":
            value = (c.get("patient") or {}).get("age_days")
            if value is None:
                return []
            kind, unit = "measurement", "hari"
        else:
            return None
        return [
            {
                "field": fld,
                "kind": kind,
                "status": "present",
                "value": value,
                "unit": unit,
                "provenance": {"method": "db_query", "source_id": "claim_header"},
            }
        ]

    def facts_for(self, fld: str) -> list:
        header = self._header_facts(fld)
        if header is not None:
            return header
        return [f for f in self.facts if f["field"] == fld]


# --------------------------------------------------------------------------------------
# Fakta turunan (P/F ratio, delta pCO2, leukositosis)
# --------------------------------------------------------------------------------------
def _derived(fld, kind, value, unit, observed_at, derived_from) -> dict:
    return {
        "field": fld,
        "kind": kind,
        "status": "present",
        "value": value,
        "unit": unit,
        "observed_at": observed_at,
        "provenance": {"method": "rule_derived", "derived_from": derived_from},
    }


def derive_facts(doc: dict, opts: Options) -> dict:
    """Kembalikan salinan dokumen dengan fakta turunan ditambahkan.
    Bila fakta langsung dari database sudah ada untuk field turunan, tidak dihitung ulang.
    """
    doc = copy.deepcopy(doc)
    facts = doc.setdefault("facts", [])

    def present(fld):
        return [f for f in facts if f["field"] == fld and f["status"] == "present"]

    def has_direct(fld):
        return any(
            f["field"] == fld and f["provenance"].get("method") != "rule_derived"
            for f in facts
        )

    if not has_direct(
        "bga.pf_ratio"
    ):  # P/F = pO2 / FiO2 pada waktu pengukuran yang sama
        for po2 in present("bga.po2"):
            for fio2 in present("bga.fio2"):
                same_time = po2.get("observed_at") and po2["observed_at"] == fio2.get(
                    "observed_at"
                )
                if same_time and fio2["value"] > 0:
                    facts.append(
                        _derived(
                            "bga.pf_ratio",
                            "measurement",
                            round(po2["value"] / fio2["value"], 1),
                            "ratio",
                            po2["observed_at"],
                            ["bga.po2", "bga.fio2"],
                        )
                    )

    if not has_direct(
        "bga.pco2_delta_from_baseline"
    ):  # selisih terhadap pCO2 paling awal
        pco2 = sorted(
            [f for f in present("bga.pco2") if f.get("observed_at")],
            key=lambda f: f["observed_at"],
        )
        for later in pco2[1:]:
            facts.append(
                _derived(
                    "bga.pco2_delta_from_baseline",
                    "measurement",
                    round(later["value"] - pco2[0]["value"], 1),
                    "mmHg",
                    later["observed_at"],
                    ["bga.pco2"],
                )
            )

    thr = opts.derivation.get("leukosit_tinggi_threshold")
    if thr is not None and not has_direct("lab.leukosit_tinggi"):
        for f in present("lab.leukosit"):
            facts.append(
                _derived(
                    "lab.leukosit_tinggi",
                    "flag",
                    f["value"] > thr,
                    None,
                    f.get("observed_at"),
                    ["lab.leukosit"],
                )
            )
    return doc


# --------------------------------------------------------------------------------------
# Evaluasi kondisi (daun)
# --------------------------------------------------------------------------------------
SET_OPS = {"contains_any", "contains_all", "has_code", "not_has_code"}
COUNT_OPS = {"count_gte", "count_lte"}
SCALAR_OPS = {"eq", "ne", "lt", "lte", "gt", "gte", "between", "in"}
ALL_OPS = SET_OPS | COUNT_OPS | SCALAR_OPS | {"exists", "not_exists"}


def _cmp(op: str, v: Any, ref: Any) -> Optional[bool]:
    try:
        if op == "eq":
            return v == ref
        if op == "ne":
            return v != ref
        if op == "lt":
            return v < ref
        if op == "lte":
            return v <= ref
        if op == "gt":
            return v > ref
        if op == "gte":
            return v >= ref
        if op == "between":
            return ref[0] <= v <= ref[1]
        if op == "in":
            return v in ref
    except TypeError:
        return U
    raise ValueError(f"operator tidak dikenal: {op}")


def _evidence(f: dict) -> dict:
    p = f.get("provenance", {})
    raw = {
        "value": f.get("value"),
        "unit": f.get("unit"),
        "observed_at": f.get("observed_at"),
        "method": p.get("method"),
        "source": p.get("source_id"),
        "record_id": p.get("record_id"),
        "document_id": p.get("document_id"),
        "text_span": p.get("text_span"),
    }
    if f.get("conflict_details"):
        raw["conflicts"] = [
            {"value": detail["value"], "provenance": detail["provenance"]}
            for detail in f["conflict_details"]
        ]
    return {k: v for k, v in raw.items() if v is not None and v != []}


def _eval_present(op: str, c: dict, present: list) -> tuple:
    """Evaluasi operator terhadap fakta berstatus present. Mengembalikan (tri, alasan)."""
    ref = c.get("value")
    agg = c.get("aggregate", "any")

    if op == "exists":
        return T, f"{len(present)} fakta ditemukan"
    if op == "not_exists":
        return F, f"{len(present)} fakta ditemukan"

    if op in SET_OPS:
        pool: list = []
        for f in present:
            v = f["value"]
            pool.extend(v if isinstance(v, list) else [v])
        refs = ref if isinstance(ref, list) else [ref]
        if op in ("has_code", "not_has_code"):
            hit = any(
                code_matches(code, p)
                for code in pool
                if isinstance(code, str)
                for p in refs
            )
            ok = hit if op == "has_code" else not hit
            return (
                ok,
                f"kode {'ditemukan' if hit else 'tidak ditemukan'} untuk pola {refs}",
            )
        ok = (
            any(r in pool for r in refs)
            if op == "contains_any"
            else all(r in pool for r in refs)
        )
        return ok, f"nilai tersedia: {sorted(set(map(str, pool)))}"

    if op in COUNT_OPS:
        n = len(present)
        return (n >= ref if op == "count_gte" else n <= ref), f"jumlah fakta = {n}"

    # operator skalar
    unit = c.get("unit")
    if unit:
        bad = [f for f in present if f.get("unit") not in (None, unit)]
        if bad:
            return U, f"satuan tidak cocok: {bad[0].get('unit')} != {unit}"
    # catatan: urut waktu memakai string ISO-8601; cukup untuk zona waktu yang sama
    ordered = sorted(
        present,
        key=lambda f: (f.get("observed_at") is None, f.get("observed_at") or ""),
    )
    values = [f["value"] for f in ordered]
    if agg in ("any", "all"):
        rs = [_cmp(op, v, ref) for v in values]
        return (tri_any(rs) if agg == "any" else tri_all(rs)), f"nilai: {values}"
    if agg == "count":
        return _cmp(op, len(values), ref), f"jumlah = {len(values)}"
    try:
        pick = {
            "min": min,
            "max": max,
            "first": lambda x: x[0],
            "latest": lambda x: x[-1],
        }[agg](values)
    except TypeError:
        return U, f"agregat '{agg}' tidak bisa dihitung untuk nilai non-numerik"
    return _cmp(op, pick, ref), f"{agg} = {pick}"


def eval_condition(c: dict, ctx: Context) -> tuple:
    fld, op = c["field"], c["op"]
    on_missing = c.get("on_missing", "review")
    trace = {
        "kind": "condition",
        "label": c.get("label") or f"{fld} {op} {c.get('value')}",
        "field": fld,
        "op": op,
        "value": c.get("value"),
        "aggregate": c.get("aggregate", "any"),
    }

    def done(res, reason, used=None):
        trace["result"], trace["reason"] = TRI_LABEL[res], reason
        trace["evidence"] = [_evidence(f) for f in (used or [])][:10]
        return res, trace

    all_facts = ctx.facts_for(fld)
    usable, low = [], []
    for f in all_facts:
        conf = f.get("confidence")
        if (
            f["provenance"].get("method") == "llm_extraction"
            and conf is not None
            and conf < ctx.opts.min_confidence
        ):
            low.append(f)
        else:
            usable.append(f)
    present = [f for f in usable if f["status"] == "present"]
    conflicting = [f for f in usable if f["status"] == "conflicting"]
    absent = [f for f in usable if f["status"] == "absent"]

    if not all_facts:
        return done(
            F if on_missing == "fail" else U,
            f"tidak terdokumentasi (on_missing={on_missing})",
        )
    if not (present or conflicting or absent):
        return done(U, "hanya ada fakta ber-confidence rendah", low)

    if present:
        res, reason = _eval_present(op, c, present)
        if res is False and (conflicting or low):
            return done(
                U,
                reason + "; ada fakta konflik/confidence rendah pada field yang sama",
                present + conflicting + low,
            )
        return done(res, reason, present)
    if conflicting:
        return done(U, "sumber saling bertentangan", conflicting)
    # hanya fakta 'absent': sumber eksplisit menyatakan tidak ada
    return done(
        T if op == "not_exists" else F, "sumber eksplisit menyatakan tidak ada", absent
    )


# --------------------------------------------------------------------------------------
# Evaluasi pohon logika
# --------------------------------------------------------------------------------------
def eval_node(n: dict, ctx: Context) -> tuple:
    if "field" in n:
        return eval_condition(n, ctx)
    label = n.get("label")
    if "all" in n or "any" in n:
        kind = "all" if "all" in n else "any"
        kids = [eval_node(k, ctx) for k in n[kind]]
        res = (tri_all if kind == "all" else tri_any)([r for r, _ in kids])
        return res, {
            "kind": kind,
            "label": label,
            "result": TRI_LABEL[res],
            "children": [t for _, t in kids],
        }
    if "not" in n:
        r, t = eval_node(n["not"], ctx)
        res = tri_not(r)
        return res, {
            "kind": "not",
            "label": label,
            "result": TRI_LABEL[res],
            "children": [t],
        }
    if "at_least" in n:
        spec = n["at_least"]
        kids = [eval_node(k, ctx) for k in spec["of"]]
        res = tri_at_least(spec["n"], [r for r, _ in kids])
        return res, {
            "kind": f"at_least_{spec['n']}",
            "label": label,
            "result": TRI_LABEL[res],
            "children": [t for _, t in kids],
        }
    raise ValueError(f"node tidak dikenal: {list(n)}")


def iter_conditions(n: dict) -> Iterator[dict]:
    if "field" in n:
        yield n
    elif "all" in n or "any" in n:
        for k in n.get("all") or n.get("any"):
            yield from iter_conditions(k)
    elif "not" in n:
        yield from iter_conditions(n["not"])
    elif "at_least" in n:
        for k in n["at_least"]["of"]:
            yield from iter_conditions(k)


# --------------------------------------------------------------------------------------
# Evaluasi aturan & klaim
# --------------------------------------------------------------------------------------
def _applicability(rule: dict, ctx: Context, diagnosis_index: Optional[int] = None) -> tuple:
    """Kembalikan (kode_yang_cocok, None) bila berlaku, atau (None, alasan) bila tidak."""
    claim = ctx.claim
    if rule["scope"] != "ALL" and rule["scope"] != claim["encounter_type"]:
        return (
            None,
            f"scope {rule['scope']} tidak cocok dengan klaim {claim['encounter_type']}",
        )
    ref_date = (
        claim.get("discharge_date")
        or claim.get("visit_date")
        or claim.get("admit_date")
    )
    if ref_date:  # string ISO-8601 bisa dibandingkan langsung
        if rule.get("effective_from") and ref_date < rule["effective_from"]:
            return None, "aturan belum berlaku pada tanggal klaim"
        if rule.get("effective_to") and ref_date > rule["effective_to"]:
            return None, "aturan sudah tidak berlaku pada tanggal klaim"
    trig = rule["trigger"]
    pos = trig.get("position", "any")
    if trig.get("code_system", "ICD10") == "ICD10":
        diagnoses = claim.get("diagnoses", [])
        if diagnosis_index is not None:
            diagnoses = [diagnoses[diagnosis_index]]
        items = [(d["code"], d["position"]) for d in diagnoses]
    else:
        items = [(p["code"], "any") for p in claim.get("procedures", [])]
    matched = [
        code
        for code, p in items
        if (pos == "any" or p == pos)
        and any(code_matches(code, pat) for pat in trig["codes"])
    ]
    if not matched:
        return None, "trigger kode tidak cocok"
    return matched, None


def evaluate_rule(
    rule: dict, ctx: Context, diagnosis_index: Optional[int] = None
) -> dict:
    src = rule.get("source", {})
    reconciliation_status = src.get("reconciliation_status")
    source_verified = bool(src.get("verified_against_original"))
    effective_reconciliation = reconciliation_status or "unverified"
    reconciled = effective_reconciliation == "verified"
    base = {
        "rule_id": rule["id"],
        "title": rule["title"],
        "type": rule["type"],
        "rule_status": rule["status"],
        "source": f"{src.get('document', '?')} {src.get('year', '')}".strip(),
        "verified_against_original": source_verified,
        "source_details": {
            **copy.deepcopy(src),
            "reconciliation_status": effective_reconciliation,
            "lineage": ctx.rule_lineage,
        },
    }
    matched, why = _applicability(rule, ctx, diagnosis_index)
    if matched is None:
        return {**base, "status": "NOT_APPLICABLE", "message": why}

    review_reasons = []
    if rule["status"] not in ctx.opts.include_statuses:
        review_reasons.append("status aturan tidak termasuk dalam status evaluasi yang dipilih")
    if rule["status"] != "active":
        review_reasons.append(f"status aturan '{rule['status']}' belum aktif untuk keputusan final")
    if not source_verified:
        review_reasons.append("aturan belum diverifikasi terhadap dokumen sumber asli")
    if reconciliation_status == "disputed":
        review_reasons.append("terdapat perbedaan sumber aturan yang belum direkonsiliasi")
    elif reconciliation_status == "unverified":
        review_reasons.append("aturan belum direkonsiliasi terhadap rantai sumber")
    elif not reconciled:
        review_reasons.append("status rekonsiliasi aturan belum terverifikasi")
    if rule.get("open_questions"):
        review_reasons.append("aturan memiliki pertanyaan terbuka yang belum diselesaikan")

    parts, comps = {}, []
    for key in ("evidence", "treatment", "extra_conditions"):
        if key in rule:
            res, tr = eval_node(rule[key], ctx)
            comps.append(res)
            parts[key] = tr
    if "violation_when" in rule:
        res, tr = eval_node(rule["violation_when"], ctx)
        tr["note"] = "TRUE berarti aturan dilanggar"
        comps.append(tri_not(res))
        parts["violation_when"] = tr

    def missing_fields(trace: Any) -> list[str]:
        if not isinstance(trace, dict):
            return []
        if (
            trace.get("kind") == "condition"
            and trace.get("result") == "U"
            and trace.get("reason", "").startswith(
                ("tidak terdokumentasi", "hanya ada fakta ber-confidence rendah")
            )
        ):
            return [trace["field"]]
        return [
            field_name
            for child in trace.values()
            for field_name in (
                missing_fields(child)
                if isinstance(child, (dict, list))
                else []
            )
        ]

    tri = tri_all(comps) if comps else U
    status = {T: "PASS", F: "FAIL", U: "REVIEW"}[tri]
    missing_fields_found = list(
        dict.fromkeys(field_name for trace in parts.values() for field_name in missing_fields(trace))
    )

    available = set(ctx.claim.get("documents_available", []))
    missing = [d for d in rule.get("required_documents", []) if d not in available]
    if missing and status == "PASS":
        status = "FAIL" if ctx.opts.missing_document_policy == "fail" else "REVIEW"
    if review_reasons:
        status = "REVIEW"

    outcome = rule["outcome"]
    message = {
        "PASS": outcome["pass_message"],
        "FAIL": outcome["fail_message"],
        "REVIEW": outcome.get("review_message")
        or "Data belum cukup; perlu review manual.",
    }[status]
    if not comps:
        message = "Aturan tidak punya kriteria; perlu diperbaiki."
    if missing:
        message += " Dokumen belum ada: " + ", ".join(missing) + "."
    if review_reasons:
        message += " Perlu tinjauan: " + "; ".join(review_reasons) + "."

    actions = []
    if status == "FAIL":
        actions.append(outcome.get("action_on_fail", "flag"))
    if status == "REVIEW":
        actions.append("manual_review")
    if missing:
        actions.append("request_document")
    severity = {
        "PASS": "info",
        "REVIEW": "warning",
        "FAIL": outcome.get("severity", "error"),
    }[status]
    return {
        **base,
        "status": status,
        "message": message,
        "severity": severity,
        "matched_codes": matched,
        "actions": list(dict.fromkeys(actions)),
        "suggest_codes": outcome.get("suggest_codes", []) if status == "FAIL" else [],
        "missing_documents": missing,
        "missing_fields": missing_fields_found,
        "trace": parts,
    }


def validate_claim_document(doc: dict) -> None:
    """Validate the claim and evidence fields consumed by the evaluator."""
    if not isinstance(doc, dict):
        raise ValueError("claim document must be an object")
    claim = doc.get("claim")
    if not isinstance(claim, dict):
        raise ValueError("claim must be an object")
    if not isinstance(claim.get("claim_id"), str) or not claim["claim_id"].strip():
        raise ValueError("claim.claim_id must be a non-empty string")
    if claim.get("encounter_type") not in {"RI", "RJ"}:
        raise ValueError("claim.encounter_type must be 'RI' or 'RJ'")

    diagnoses = claim.get("diagnoses")
    if not isinstance(diagnoses, list):
        raise ValueError("claim.diagnoses must be an array")
    for index, diagnosis in enumerate(diagnoses):
        path = f"claim.diagnoses[{index}]"
        if not isinstance(diagnosis, dict):
            raise ValueError(f"{path} must be an object")
        if not isinstance(diagnosis.get("code"), str) or not diagnosis["code"].strip():
            raise ValueError(f"{path}.code must be a non-empty string")
        if diagnosis.get("position") not in {"primary", "secondary"}:
            raise ValueError(f"{path}.position must be 'primary' or 'secondary'")
        sequence = diagnosis.get("sequence")
        if sequence is not None and (
            not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1
        ):
            raise ValueError(f"{path}.sequence must be a positive integer")

    documents = claim.get("documents_available", [])
    if not isinstance(documents, list) or any(not isinstance(item, str) for item in documents):
        raise ValueError("claim.documents_available must be an array of strings")

    procedures = claim.get("procedures", [])
    if not isinstance(procedures, list):
        raise ValueError("claim.procedures must be an array")
    for index, procedure in enumerate(procedures):
        if not isinstance(procedure, dict) or not isinstance(procedure.get("code"), str) or not procedure["code"].strip():
            raise ValueError(f"claim.procedures[{index}].code must be a non-empty string")

    facts = doc.get("facts", [])
    if not isinstance(facts, list):
        raise ValueError("facts must be an array")
    valid_kinds = {"measurement", "category", "flag", "category_list", "text", "event"}
    valid_statuses = {"present", "absent", "conflicting"}
    valid_methods = {"db_query", "llm_extraction", "rule_derived", "manual_entry"}
    for index, fact in enumerate(facts):
        path = f"facts[{index}]"
        if not isinstance(fact, dict):
            raise ValueError(f"{path} must be an object")
        if not isinstance(fact.get("field"), str) or not fact["field"].strip():
            raise ValueError(f"{path}.field must be a non-empty string")
        if fact.get("kind") not in valid_kinds:
            raise ValueError(f"{path}.kind is unsupported")
        status = fact.get("status")
        if status not in valid_statuses:
            raise ValueError(f"{path}.status must be present, absent, or conflicting")
        if status == "present" and "value" not in fact:
            raise ValueError(f"{path}.value is required when status is present")
        provenance = fact.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("method") not in valid_methods:
            raise ValueError(f"{path}.provenance.method is missing or unsupported")
        confidence = fact.get("confidence")
        if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise ValueError(f"{path}.confidence must be between 0 and 1")
        if status == "conflicting":
            details = fact.get("conflict_details")
            if not isinstance(details, list) or len(details) < 2:
                raise ValueError(f"{path}.conflict_details must contain at least two sources")
            for detail_index, detail in enumerate(details):
                detail_provenance = detail.get("provenance") if isinstance(detail, dict) else None
                if (
                    not isinstance(detail, dict)
                    or "value" not in detail
                    or not isinstance(detail_provenance, dict)
                    or detail_provenance.get("method") not in valid_methods
                ):
                    raise ValueError(
                        f"{path}.conflict_details[{detail_index}] must include value and valid provenance"
                    )


def evaluate_claim(ruleset: dict, doc: dict, options: Optional[Options] = None) -> dict:
    validate_claim_document(doc)
    opts = options or Options()
    n_before = len(doc.get("facts", []))
    doc = derive_facts(doc, opts)
    added_by_engine = doc["facts"][n_before:]  # derive_facts hanya menambah di akhir
    ctx = Context(doc, opts, ruleset.get("ruleset", {}).get("lineage"))
    results = [evaluate_rule(r, ctx) for r in ruleset["rules"]]
    diagnosis_results = []
    diagnosis_rules = [
        rule
        for rule in ruleset["rules"]
        if rule["trigger"].get("code_system", "ICD10") == "ICD10"
    ]
    for index, diagnosis in enumerate(ctx.claim.get("diagnoses", [])):
        rule_results = [
            result
            for rule in diagnosis_rules
            if (result := evaluate_rule(rule, ctx, index))["status"]
            != "NOT_APPLICABLE"
        ]
        if any(result["status"] == "FAIL" for result in rule_results):
            status = "FAIL"
            message = "Setidaknya satu aturan diagnosis yang cocok dinilai tidak sesuai."
        elif any(result["status"] == "REVIEW" for result in rule_results):
            status = "REVIEW"
            message = "Sedikitnya satu aturan diagnosis yang cocok memerlukan tinjauan manual."
        elif rule_results:
            status = "PASS"
            message = "Semua aturan diagnosis yang cocok dinilai sesuai."
        else:
            status = "NOT_APPLICABLE"
            message = "Tidak ada aturan diagnosis yang cocok dengan kode, layanan, dan posisi ini."
        diagnosis_results.append(
            {
                "diagnosis_index": index,
                "diagnosis": copy.deepcopy(diagnosis),
                "status": status,
                "message": message,
                "rule_results": rule_results,
            }
        )
    counts = Counter(r["status"] for r in results)
    diagnosis_counts = Counter(r["status"] for r in diagnosis_results)
    if diagnosis_counts["FAIL"]:
        overall = "FAIL"
    elif diagnosis_counts["REVIEW"]:
        overall = "REVIEW"
    elif diagnosis_counts["PASS"]:
        overall = "PASS"
    else:
        overall = "NOT_APPLICABLE"
    return {
        "claim_id": doc["claim"]["claim_id"],
        "overall": overall,
        "counts": dict(counts),
        "diagnosis_counts": dict(diagnosis_counts),
        "results": results,
        "diagnosis_results": diagnosis_results,
        "derived_facts": added_by_engine,
        "unverified_rules_used": sorted(
            {
                r["rule_id"]
                for r in results
                if r["status"] != "NOT_APPLICABLE"
                and (
                    not r["verified_against_original"]
                    or r["source_details"].get("reconciliation_status")
                    in {"unverified", "disputed"}
                )
            }
        ),
    }


# --------------------------------------------------------------------------------------
# Lint: cek aturan terhadap katalog field sebelum dijalankan
# --------------------------------------------------------------------------------------
OPS_BY_KIND = {
    "measurement": {
        "lt",
        "lte",
        "gt",
        "gte",
        "eq",
        "ne",
        "between",
        "in",
        "exists",
        "not_exists",
        "count_gte",
        "count_lte",
    },
    "flag": {"eq", "ne", "exists", "not_exists"},
    "category": {"eq", "ne", "in", "exists", "not_exists"},
    "category_list": {
        "contains_any",
        "contains_all",
        "exists",
        "not_exists",
        "has_code",
        "not_has_code",
        "count_gte",
        "count_lte",
    },
    "text": {"exists", "not_exists", "contains_any"},
    "event": {"exists", "not_exists", "count_gte", "count_lte"},
}


def lint_rules(ruleset: dict, catalog: dict) -> list:
    issues = []
    cat = {f["path"]: f for f in catalog["fields"]}
    seen = set()

    def add(level, rid, msg):
        issues.append({"level": level, "rule_id": rid, "message": msg})

    for r in ruleset["rules"]:
        rid = r["id"]
        if rid in seen:
            add("error", rid, "ID aturan duplikat")
        seen.add(rid)
        crit = [
            k
            for k in ("evidence", "treatment", "extra_conditions", "violation_when")
            if k in r
        ]
        if not crit:
            add(
                "error",
                rid,
                "aturan tidak punya kriteria (evidence/treatment/extra_conditions/violation_when)",
            )
        if "violation_when" in r and ("evidence" in r or "treatment" in r):
            add(
                "warning",
                rid,
                "violation_when digabung dengan evidence/treatment; pastikan memang disengaja",
            )
        source = r["source"]
        reconciliation = source.get("reconciliation_status")
        if reconciliation not in {None, "verified", "unverified", "disputed"}:
            add("error", rid, f"status rekonsiliasi tidak dikenal: {reconciliation}")
        if r["status"] == "active" and (
            not source.get("verified_against_original")
            or reconciliation != "verified"
            or r.get("open_questions")
        ):
            state = reconciliation or "unverified"
            add(
                "warning",
                rid,
                f"aturan aktif memerlukan tinjauan sumber (rekonsiliasi={state}, "
                f"pertanyaan_terbuka={len(r.get('open_questions', []))})",
            )
        known_docs = set(catalog.get("document_types", []))
        for d in r.get("required_documents", []):
            if known_docs and d not in known_docs:
                add(
                    "error",
                    rid,
                    f"jenis dokumen '{d}' tidak ada di katalog (document_types)",
                )
        for k in crit:
            for c in iter_conditions(r[k]):
                fld, op = c["field"], c["op"]
                spec = cat.get(fld)
                if op not in ALL_OPS:
                    add("error", rid, f"operator tidak dikenal: {op}")
                if spec is None:
                    add("error", rid, f"field '{fld}' tidak ada di katalog")
                    continue
                if op in ALL_OPS and op not in OPS_BY_KIND.get(spec["kind"], ALL_OPS):
                    add(
                        "error",
                        rid,
                        f"operator '{op}' tidak cocok untuk field '{fld}' (kind={spec['kind']})",
                    )
                if c.get("unit") and spec.get("unit") and c["unit"] != spec["unit"]:
                    add(
                        "warning",
                        rid,
                        f"satuan '{c['unit']}' berbeda dari katalog '{spec['unit']}' untuk {fld}",
                    )
                allowed = spec.get("allowed_values")
                if allowed and op in {"contains_any", "contains_all", "in", "eq", "ne"}:
                    vals = (
                        c["value"]
                        if isinstance(c.get("value"), list)
                        else [c.get("value")]
                    )
                    for v in vals:
                        if v not in allowed:
                            add(
                                "error",
                                rid,
                                f"nilai '{v}' bukan konsep valid untuk {fld} (allowed: {allowed})",
                            )
    return issues


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _print_report(res: dict) -> None:
    print(
        f"Klaim {res['claim_id']}: hasil diagnosis = {res['overall']}  "
        f"{res['diagnosis_counts']}"
    )
    for diagnosis_result in res["diagnosis_results"]:
        diagnosis = diagnosis_result["diagnosis"]
        print(
            f"\n[{diagnosis_result['status']}] {diagnosis['code']} "
            f"({diagnosis['position']})"
        )
        print(f"  {diagnosis_result['message']}")
        for rule_result in diagnosis_result["rule_results"]:
            print(
                f"  {rule_result['rule_id']} - {rule_result['title']} "
                f"(sumber: {rule_result['source']}; "
                f"rekonsiliasi: {rule_result['source_details'].get('reconciliation_status', 'unverified')})"
            )
            print(f"    {rule_result['message']}")
            if rule_result.get("suggest_codes"):
                print(f"    saran kode: {', '.join(rule_result['suggest_codes'])}")
            if rule_result.get("actions"):
                print(f"    aksi: {', '.join(rule_result['actions'])}")
    if res["derived_facts"]:
        print(f"\nFakta turunan: {[f['field'] for f in res['derived_facts']]}")


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Engine evaluasi aturan pending klaim")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("evaluate", help="evaluasi satu klaim")
    ev.add_argument("--rules", required=True)
    ev.add_argument("--facts", required=True)
    ev.add_argument(
        "--include-statuses",
        nargs="+",
        default=["active"],
        help="status yang dapat dievaluasi; aturan cocok di luar daftar tetap REVIEW",
    )
    ev.add_argument("--min-confidence", type=float, default=0.7)
    ev.add_argument(
        "--missing-doc-policy", choices=["review", "fail"], default="review"
    )
    ev.add_argument(
        "--json", action="store_true", help="keluarkan JSON lengkap termasuk trace"
    )
    li = sub.add_parser("lint", help="cek aturan terhadap katalog field")
    li.add_argument("--rules", required=True)
    li.add_argument("--catalog", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "lint":
        issues = lint_rules(_load(a.rules), _load(a.catalog))
        for i in issues:
            print(f"[{i['level'].upper()}] {i['rule_id']}: {i['message']}")
        print(f"{len(issues)} temuan")
        return 1 if any(i["level"] == "error" for i in issues) else 0

    opts = Options(
        include_statuses=tuple(a.include_statuses),
        min_confidence=a.min_confidence,
        missing_document_policy=a.missing_doc_policy,
    )
    res = evaluate_claim(_load(a.rules), _load(a.facts), opts)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        _print_report(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
