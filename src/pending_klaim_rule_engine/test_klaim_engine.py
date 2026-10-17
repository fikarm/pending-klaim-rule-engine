import copy
import json
import unittest
from pathlib import Path

from pending_klaim_rule_engine.klaim_engine import (
    Context,
    Options,
    derive_facts,
    eval_node,
    evaluate_claim,
    lint_rules,
    tri_all,
    tri_any,
    tri_at_least,
    tri_not,
    validate_claim_document,
)

HERE = Path(__file__).parent


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


RULES = load("rules_ba_2019.json")
CATALOG = load("field_catalog.json")
BASE = load("claim_facts_example.json")


def fact(
    field,
    value,
    kind="measurement",
    unit=None,
    status="present",
    at=None,
    method="db_query",
    **kw,
):
    f = {
        "field": field,
        "kind": kind,
        "status": status,
        "unit": unit,
        "observed_at": at,
        "provenance": {"method": method, "record_id": f"r-{field}"},
    }
    if status == "present":
        f["value"] = value
    f.update(kw)
    return f


def claim(dx, facts=None, enc="RI", docs=None, procs=()):
    return {
        "schema_version": "1.0",
        "claim": {
            "claim_id": "T",
            "encounter_type": enc,
            "discharge_date": "2026-09-05",
            "diagnoses": [{"code": c, "position": p} for c, p in dx],
            "procedures": [{"code": c} for c in procs],
            "documents_available": docs if docs is not None else [],
        },
        "facts": facts or [],
    }


def approved_ruleset():
    ruleset = copy.deepcopy(RULES)
    for rule in ruleset["rules"]:
        source = rule["source"]
        source["verified_against_original"] = True
        source["reconciliation_status"] = "verified"
        rule["open_questions"] = []
    return ruleset


def run(doc, **opt):
    return evaluate_claim(approved_ruleset(), doc, Options(**opt))


def status_of(res, rule_id):
    return next(r for r in res["results"] if r["rule_id"] == rule_id)["status"]


def one_rule(rule_id):
    return next(r for r in RULES["rules"] if r["id"] == rule_id)


class TestKleene(unittest.TestCase):
    def test_basic(self):
        self.assertIs(tri_all([True, None]), None)
        self.assertIs(tri_all([False, None]), False)
        self.assertIs(tri_any([True, None]), True)
        self.assertIs(tri_any([False, None]), None)
        self.assertIs(tri_not(None), None)
        self.assertIs(tri_at_least(2, [True, True, None]), True)
        self.assertIs(tri_at_least(2, [True, None, None]), None)
        self.assertIs(tri_at_least(2, [True, False, False]), False)


class TestHipokalemia(unittest.TestCase):
    DOCS = ["hasil_lab", "resume_medis"]

    def make(self, kalium_values, drugs=("kcl_injeksi",), docs=None):
        facts = [
            fact("lab.kalium", v, unit="mmol/L", at=f"2026-09-0{i + 1}T08:00:00+07:00")
            for i, v in enumerate(kalium_values)
        ]
        if drugs is not None:
            facts.append(fact("therapy.drugs", list(drugs), kind="category_list"))
        return claim(
            [("A09", "primary"), ("E87.6", "secondary")], facts, docs=docs or self.DOCS
        )

    def test_contoh_klaim_pass(self):
        self.assertEqual(status_of(run(BASE), "RI-HIPOKALEMIA"), "PASS")

    def test_kalium_normal_fail(self):
        self.assertEqual(
            status_of(run(self.make([3.4, 3.6])), "RI-HIPOKALEMIA"), "FAIL"
        )

    def test_salah_satu_pengukuran_cukup(self):
        self.assertEqual(
            status_of(run(self.make([3.4, 2.7])), "RI-HIPOKALEMIA"), "PASS"
        )

    def test_tanpa_kalium_fail_karena_on_missing_fail(self):
        self.assertEqual(status_of(run(self.make([])), "RI-HIPOKALEMIA"), "FAIL")

    def test_tanpa_terapi_fail(self):
        self.assertEqual(
            status_of(run(self.make([2.5], drugs=None)), "RI-HIPOKALEMIA"), "FAIL"
        )

    def test_dokumen_kurang_review_atau_fail(self):
        d = self.make([2.5], docs=["resume_medis"])
        res = run(d)
        r = next(x for x in res["results"] if x["rule_id"] == "RI-HIPOKALEMIA")
        self.assertEqual(r["status"], "REVIEW")
        self.assertEqual(r["missing_documents"], ["hasil_lab"])
        self.assertIn("request_document", r["actions"])
        self.assertEqual(
            status_of(run(d, missing_document_policy="fail"), "RI-HIPOKALEMIA"), "FAIL"
        )

    def test_satuan_beda_review(self):
        d = self.make([2.5])
        d["facts"][0]["unit"] = "mg/dL"
        self.assertEqual(status_of(run(d), "RI-HIPOKALEMIA"), "REVIEW")


class TestGagalNapas(unittest.TestCase):
    DOCS = ["hasil_bga", "resume_medis"]

    def make(self, facts):
        return claim([("J96.0", "secondary")], facts, docs=self.DOCS)

    def support(self, v=("nasal_kanul",)):
        return fact("therapy.respiratory_support", list(v), kind="category_list")

    def test_po2_rendah_cukup_walau_data_lain_kosong(self):
        d = self.make([fact("bga.po2", 55, unit="mmHg"), self.support()])
        self.assertEqual(status_of(run(d), "RI-GAGAL_NAPAS_AKUT"), "PASS")

    def test_hanya_spo2_normal_review(self):
        d = self.make([fact("vital.spo2", 95, unit="%"), self.support()])
        self.assertEqual(status_of(run(d), "RI-GAGAL_NAPAS_AKUT"), "REVIEW")

    def test_tanpa_tata_laksana_fail(self):
        d = self.make(
            [
                fact("bga.po2", 55, unit="mmHg"),
                fact(
                    "therapy.respiratory_support",
                    None,
                    kind="category_list",
                    status="absent",
                ),
            ]
        )
        self.assertEqual(status_of(run(d), "RI-GAGAL_NAPAS_AKUT"), "FAIL")

    def test_pf_ratio_turunan(self):
        at = "2026-09-02T10:00:00+07:00"
        d = self.make(
            [
                fact("bga.po2", 80, unit="mmHg", at=at),
                fact("bga.fio2", 0.5, unit="fraction", at=at),
                self.support(),
            ]
        )
        res = run(d)
        self.assertEqual(status_of(res, "RI-GAGAL_NAPAS_AKUT"), "PASS")
        self.assertEqual(res["derived_facts"][0]["value"], 160.0)

    def test_delta_pco2_turunan(self):
        d = claim(
            [],
            [
                fact("bga.pco2", 45, unit="mmHg", at="2026-09-01T08:00:00+07:00"),
                fact("bga.pco2", 58, unit="mmHg", at="2026-09-02T08:00:00+07:00"),
            ],
        )
        out = derive_facts(d, Options())
        deltas = [
            f["value"]
            for f in out["facts"]
            if f["field"] == "bga.pco2_delta_from_baseline"
        ]
        self.assertEqual(deltas, [13.0])


class TestKodeDanAdministratif(unittest.TestCase):
    def test_hf_dengan_i10_fail_dan_saran_i113(self):
        res = run(claim([("I50.9", "secondary"), ("I10", "secondary")]))
        r = next(x for x in res["results"] if x["rule_id"] == "RJ-HF_HIPERTENSI")
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(r["suggest_codes"], ["I11.0"])

    def test_hf_tanpa_i10_pass(self):
        self.assertEqual(
            status_of(
                run(claim([("I11.0", "primary"), ("I50.9", "secondary")])),
                "RJ-HF_HIPERTENSI",
            ),
            "PASS",
        )

    def test_tb_dengan_efusi_fail(self):
        self.assertEqual(
            status_of(
                run(claim([("A16.2", "primary"), ("J90", "secondary")])),
                "RJ-TB_PARU_EKSKLUSI",
            ),
            "FAIL",
        )

    def test_tb_tanpa_efusi_pass(self):
        self.assertEqual(
            status_of(run(claim([("A16.2", "primary")])), "RJ-TB_PARU_EKSKLUSI"), "PASS"
        )

    def test_scope_tidak_cocok(self):
        res = run(claim([("D56.1", "primary")], enc="RI"))
        self.assertEqual(status_of(res, "RJ-THALASEMIA_KELASI_BESI"), "NOT_APPLICABLE")

    def thal(self, count, drugs=("deferasirox",)):
        facts = [fact("therapy.drugs", list(drugs), kind="category_list")]
        if count is not None:
            facts.append(
                fact("history.iron_chelation_claims_this_month", count, unit="count")
            )
        return claim(
            [("D56.1", "primary")],
            facts,
            enc="RJ",
            docs=["protokol_pemberian_kelasi_besi", "product_batch_obat"],
        )

    def test_thalasemia_pass_fail_review(self):
        self.assertEqual(
            status_of(run(self.thal(1)), "RJ-THALASEMIA_KELASI_BESI"), "PASS"
        )
        self.assertEqual(
            status_of(run(self.thal(2)), "RJ-THALASEMIA_KELASI_BESI"), "FAIL"
        )
        self.assertEqual(
            status_of(run(self.thal(None)), "RJ-THALASEMIA_KELASI_BESI"), "REVIEW"
        )


class TestSepsisDanStatusAturan(unittest.TestCase):
    OPTS = dict(include_statuses=("active", "needs_clarification"))
    MGMT = fact("therapy.sepsis_management", ["antibiotik_iv"], kind="category_list")
    DOCS = ["resume_medis"]

    def test_needs_clarification_tetap_review_secara_default(self):
        self.assertEqual(
            status_of(run(claim([("A41.9", "primary")])), "RI-SEPSIS"), "REVIEW"
        )

    def run_verified_sepsis(self, doc):
        ruleset = approved_ruleset()
        next(r for r in ruleset["rules"] if r["id"] == "RI-SEPSIS")["status"] = "active"
        return evaluate_claim(ruleset, doc, Options(include_statuses=("active",)))

    def test_dua_kriteria_vital_cukup_sesuai_teks_ba(self):
        facts = [
            fact("vital.nadi", 110, unit="x/menit"),
            fact("vital.rr", 26, unit="x/menit"),
            self.MGMT,
        ]
        self.assertEqual(
            status_of(
                self.run_verified_sepsis(claim([("A41.9", "primary")], facts, docs=self.DOCS)),
                "RI-SEPSIS",
            ),
            "PASS",
        )

    def test_satu_kriteria_saja_review(self):
        facts = [fact("vital.nadi", 110, unit="x/menit"), self.MGMT]
        self.assertEqual(
            status_of(
                self.run_verified_sepsis(claim([("A41.9", "primary")], facts, docs=self.DOCS)),
                "RI-SEPSIS",
            ),
            "REVIEW",
        )

    def test_tanpa_tata_laksana_fail(self):
        facts = [
            fact("vital.nadi", 110, unit="x/menit"),
            fact("vital.rr", 26, unit="x/menit"),
        ]
        self.assertEqual(
            status_of(
                self.run_verified_sepsis(claim([("A41.9", "primary")], facts, docs=self.DOCS)),
                "RI-SEPSIS",
            ),
            "FAIL",
        )

    def test_kriteria_keempat_butuh_leukositosis_dan_kultur(self):
        facts = [
            fact("vital.nadi", 110, unit="x/menit"),
            fact("lab.leukosit_tinggi", True, kind="flag"),
            fact("lab.kultur_darah_positif", True, kind="flag"),
            self.MGMT,
        ]
        self.assertEqual(
            status_of(
                self.run_verified_sepsis(claim([("A41.9", "primary")], facts, docs=self.DOCS)),
                "RI-SEPSIS",
            ),
            "PASS",
        )


class TestKualitasData(unittest.TestCase):
    RULE = {
        "id": "ALL-DEMAM",
        "title": "uji",
        "type": "clinical_validation",
        "scope": "ALL",
        "status": "active",
        "trigger": {"codes": ["J18.*"]},
        "evidence": {"field": "symptom.demam", "op": "eq", "value": True},
        "outcome": {"pass_message": "ok", "fail_message": "gagal"},
        "source": {
            "document": "uji",
            "origin_note": "uji",
            "verified_against_original": True,
            "reconciliation_status": "verified",
        },
    }

    def go(self, facts):
        d = claim([("J18.9", "primary")], facts)
        return evaluate_claim({"rules": [self.RULE]}, d, Options())["results"][0][
            "status"
        ]

    def test_confidence_rendah_review(self):
        f = fact(
            "symptom.demam", True, kind="flag", method="llm_extraction", confidence=0.5
        )
        self.assertEqual(self.go([f]), "REVIEW")

    def test_confidence_tinggi_pass(self):
        f = fact(
            "symptom.demam", True, kind="flag", method="llm_extraction", confidence=0.9
        )
        self.assertEqual(self.go([f]), "PASS")

    def test_konflik_review(self):
        f = fact(
            "symptom.demam",
            None,
            kind="flag",
            status="conflicting",
            conflict_details=[
                {"value": True, "provenance": {"method": "db_query"}},
                {"value": False, "provenance": {"method": "llm_extraction"}},
            ],
        )
        self.assertEqual(self.go([f]), "REVIEW")

    def test_absent_fail(self):
        self.assertEqual(
            self.go([fact("symptom.demam", None, kind="flag", status="absent")]), "FAIL"
        )

    def test_bukti_konflik_menampilkan_nilai_dan_provenance_kedua_sumber(self):
        conflicting = fact(
            "symptom.demam",
            None,
            kind="flag",
            status="conflicting",
            conflict_details=[
                {
                    "value": True,
                    "provenance": {"method": "db_query", "source_id": "vital"},
                },
                {
                    "value": False,
                    "provenance": {
                        "method": "llm_extraction",
                        "source_id": "resume_medis",
                    },
                },
            ],
        )
        result = evaluate_claim(
            {"rules": [self.RULE]}, claim([("J18.9", "primary")], [conflicting])
        )["diagnosis_results"][0]["rule_results"][0]

        self.assertEqual(result["status"], "REVIEW")
        conflict_sources = result["trace"]["evidence"]["evidence"][0]["conflicts"]
        self.assertEqual([source["value"] for source in conflict_sources], [True, False])
        self.assertEqual(
            [source["provenance"]["source_id"] for source in conflict_sources],
            ["vital", "resume_medis"],
        )

    def test_bukti_hilang_dan_dokumen_kurang_menyebutkan_tindak_lanjut(self):
        missing_fact = evaluate_claim(
            {"rules": [self.RULE]}, claim([("J18.9", "primary")])
        )["diagnosis_results"][0]["rule_results"][0]
        self.assertEqual(missing_fact["status"], "REVIEW")
        self.assertEqual(missing_fact["missing_fields"], ["symptom.demam"])
        self.assertIn("manual_review", missing_fact["actions"])

        rule_with_document = copy.deepcopy(self.RULE)
        rule_with_document["required_documents"] = ["resume_medis"]
        missing_document = evaluate_claim(
            {"rules": [rule_with_document]},
            claim([("J18.9", "primary")], [flag("symptom.demam")]),
        )["diagnosis_results"][0]["rule_results"][0]
        self.assertEqual(missing_document["status"], "REVIEW")
        self.assertEqual(missing_document["missing_documents"], ["resume_medis"])
        self.assertIn("request_document", missing_document["actions"])
        self.assertIn("manual_review", missing_document["actions"])


class TestAtLeast(unittest.TestCase):
    NODE = {
        "at_least": {
            "n": 2,
            "of": [
                {"field": "vital.nadi", "op": "gt", "value": 90},
                {"field": "vital.rr", "op": "gt", "value": 20},
                {"field": "vital.suhu", "op": "gt", "value": 38.5},
            ],
        }
    }

    def ev(self, facts):
        ctx = Context(claim([], facts), Options())
        return eval_node(self.NODE, ctx)[0]

    def test_cases(self):
        self.assertIs(self.ev([fact("vital.nadi", 100), fact("vital.rr", 25)]), True)
        self.assertIs(self.ev([fact("vital.nadi", 100)]), None)
        self.assertIs(
            self.ev(
                [fact("vital.nadi", 100), fact("vital.rr", 18), fact("vital.suhu", 37)]
            ),
            False,
        )


class TestLint(unittest.TestCase):
    def test_contoh_aturan_tanpa_error(self):
        errors = [i for i in lint_rules(RULES, CATALOG) if i["level"] == "error"]
        self.assertEqual(errors, [])

    def test_lint_menangkap_masalah(self):
        bad = copy.deepcopy(RULES)
        bad["rules"][0]["treatment"]["value"] = ["KCl injeksi"]  # bukan konsep katalog
        bad["rules"][0]["evidence"]["field"] = "lab.tidak_ada"  # field tidak ada
        bad["rules"][1]["treatment"]["op"] = "lt"  # operator salah untuk category_list
        msgs = " ".join(
            i["message"] for i in lint_rules(bad, CATALOG) if i["level"] == "error"
        )
        self.assertIn("bukan konsep valid", msgs)
        self.assertIn("tidak ada di katalog", msgs)
        self.assertIn("tidak cocok untuk field", msgs)


def flag(field, v=True, **kw):
    return fact(field, v, kind="flag", **kw)


def cats(field, v):
    return (
        fact(field, v, kind="category", **kw)
        if False
        else fact(field, v, kind="category")
    )


class TestAturanBaru(unittest.TestCase):
    def st(self, rid, doc, **opt):
        return status_of(run(doc, **opt), rid)

    # --- pneumonia
    def test_pneumonia(self):
        base = [
            flag("imaging.thorax_infiltrat_baru"),
            fact("therapy.pneumonia_management", ["antibiotik"], kind="category_list"),
        ]
        docs = ["hasil_imaging_thorax", "resume_medis"]
        dx = [("J18.9", "primary")]
        ok = base + [flag("symptom.demam"), fact("lab.leukosit", 12500, unit="/uL")]
        self.assertEqual(self.st("RI-PNEUMONIA", claim(dx, ok, docs=docs)), "PASS")
        satu = base + [flag("symptom.demam")]
        self.assertEqual(self.st("RI-PNEUMONIA", claim(dx, satu, docs=docs)), "REVIEW")
        normal = base + [
            flag("symptom.demam", False),
            fact("lab.leukosit", 7000, unit="/uL"),
            flag("symptom.batuk_bertambah", False),
            flag("symptom.dahak_purulen", False),
            flag("exam.konsolidasi_ronki", False),
        ]
        self.assertEqual(self.st("RI-PNEUMONIA", claim(dx, normal, docs=docs)), "FAIL")
        leuko_rendah = base + [
            flag("symptom.demam"),
            fact("lab.leukosit", 3900, unit="/uL"),
        ]
        self.assertEqual(
            self.st("RI-PNEUMONIA", claim(dx, leuko_rendah, docs=docs)), "PASS"
        )

    # --- gagal napas kronis
    def test_gagal_napas_kronis(self):
        ok = [
            fact("bga.pco2", 60, unit="mmHg"),
            fact("bga.hco3", 30, unit="mmol/L"),
            fact("bga.ph", 7.40, unit="pH"),
            fact("bga.po2", 55, unit="mmHg"),
            fact("therapy.respiratory_support", ["cpap"], kind="category_list"),
        ]
        docs = ["hasil_bga", "resume_medis"]
        dx = [("J96.1", "secondary")]
        self.assertEqual(
            self.st("RI-GAGAL_NAPAS_KRONIS", claim(dx, ok, docs=docs)), "PASS"
        )
        asidosis = [f for f in ok if f["field"] != "bga.ph"] + [
            fact("bga.ph", 7.28, unit="pH")
        ]
        self.assertEqual(
            self.st("RI-GAGAL_NAPAS_KRONIS", claim(dx, asidosis, docs=docs)), "FAIL"
        )

    # --- infark, abses hati
    def test_infark_dan_abses(self):
        self.assertEqual(
            self.st(
                "RI-INFARK_CEREBRI",
                claim(
                    [("I63.9", "primary")],
                    [flag("imaging.ct_infark")],
                    docs=["hasil_ct_scan"],
                ),
            ),
            "PASS",
        )
        res = run(
            claim(
                [("I63.9", "primary")],
                [flag("imaging.ct_infark", False)],
                docs=["hasil_ct_scan"],
            )
        )
        r = next(x for x in res["results"] if x["rule_id"] == "RI-INFARK_CEREBRI")
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("I61.*", r["suggest_codes"])
        self.assertEqual(
            self.st(
                "RI-ABSES_HATI",
                claim(
                    [("K75.0", "primary")],
                    [flag("imaging.hepar_abses")],
                    docs=["hasil_usg_atau_ct"],
                ),
            ),
            "PASS",
        )

    # --- anemia RI: logic checks use a locally approved fixture
    def test_anemia_ri(self):
        d = lambda hb, trf: claim(
            [("D64.9", "secondary")],
            [fact("lab.hb", hb, unit="g/dL"), flag("therapy.transfusi_darah", trf)],
            docs=["hasil_lab", "resume_medis"],
        )
        def status(hb, transfusion):
            ruleset = approved_ruleset()
            next(r for r in ruleset["rules"] if r["id"] == "RI-ANEMIA_D64_9")["status"] = "active"
            return status_of(evaluate_claim(ruleset, d(hb, transfusion)), "RI-ANEMIA_D64_9")

        self.assertEqual(status(6.5, True), "PASS")
        self.assertEqual(status(9.0, True), "FAIL")
        self.assertEqual(status(6.5, False), "FAIL")
        self.assertEqual(self.st("RI-ANEMIA_D64_9", d(6.5, True)), "REVIEW")

    # --- asites
    def test_asites(self):
        dx = [("R18", "secondary")]
        ok = [flag("clinical.asites_masif"), flag("therapy.paracentesis_terapeutik")]
        self.assertEqual(
            self.st("RI-ASITES", claim(dx, ok, docs=["resume_medis"])), "PASS"
        )
        tanpa_pungsi = [
            flag("clinical.asites_masif"),
            flag("therapy.paracentesis_terapeutik", None, status="absent"),
        ]
        self.assertEqual(
            self.st("RI-ASITES", claim(dx, tanpa_pungsi, docs=["resume_medis"])), "FAIL"
        )
        tanpa_data_masif = [flag("therapy.paracentesis_terapeutik")]
        self.assertEqual(
            self.st("RI-ASITES", claim(dx, tanpa_data_masif, docs=["resume_medis"])),
            "REVIEW",
        )

    # --- efusi pleura
    def test_efusi_pleura(self):
        dx = [("A15.0", "primary"), ("J90", "secondary")]
        docs = ["resume_medis"]
        jalur1 = [
            flag("therapy.pungsi_pleura"),
            flag("therapy.pungsi_pleura_cairan_ditemukan"),
        ]
        self.assertEqual(
            self.st("RI-EFUSI_PLEURA", claim(dx, jalur1, docs=docs)), "PASS"
        )
        jalur2 = [
            flag("imaging.efusi_pleura"),
            flag("therapy.efusi_tatalaksana_tambahan"),
        ]
        self.assertEqual(
            self.st("RI-EFUSI_PLEURA", claim(dx, jalur2, docs=docs)), "PASS"
        )
        hanya_imaging = [
            flag("imaging.efusi_pleura"),
            flag("therapy.pungsi_pleura", False),
            flag("therapy.efusi_tatalaksana_tambahan", False),
            flag("therapy.pungsi_pleura_cairan_ditemukan", False),
        ]
        self.assertEqual(
            self.st("RI-EFUSI_PLEURA", claim(dx, hanya_imaging, docs=docs)), "FAIL"
        )
        # sebagai diagnosis utama, aturan sekunder tidak berlaku
        self.assertEqual(
            self.st("RI-EFUSI_PLEURA", claim([("J90", "primary")], jalur1, docs=docs)),
            "NOT_APPLICABLE",
        )

    # --- prosedur operasi (draft)
    def test_prosedur_operasi_draft_tetap_review(self):
        d = claim([("K35.8", "primary")], procs=["47.01"], docs=["laporan_operasi"])
        self.assertEqual(self.st("RI-PROSEDUR_OPERASI", d), "REVIEW")
        self.assertEqual(
            self.st("RI-PROSEDUR_OPERASI", d, include_statuses=("active", "draft")),
            "REVIEW",
        )

    # --- kemoterapi Z51.1
    def test_kemoterapi(self):
        docs = ["laporan_kemoterapi"]

        def d(jenis, dx2):
            return claim(
                [("Z51.1", "primary")] + dx2,
                [fact("therapy.kemoterapi", jenis, kind="category")],
                enc="RJ",
                docs=docs,
            )

        self.assertEqual(
            self.st("RJ-KEMOTERAPI_Z51_1", d("injeksi", [("C50.9", "secondary")])),
            "PASS",
        )
        self.assertEqual(self.st("RJ-KEMOTERAPI_Z51_1", d("injeksi", [])), "FAIL")
        self.assertEqual(self.st("RJ-KEMOTERAPI_Z51_1", d("oral", [])), "PASS")
        self.assertEqual(
            self.st("RJ-KEMOTERAPI_Z51_1", d("oral", [("C50.9", "secondary")])), "FAIL"
        )
        tanpa_jenis = claim(
            [("Z51.1", "primary"), ("C50.9", "secondary")], enc="RJ", docs=docs
        )
        self.assertEqual(self.st("RJ-KEMOTERAPI_Z51_1", tanpa_jenis), "REVIEW")

    # --- kontrol Z09.0
    def test_kontrol_z09_0(self):
        docs = ["resume_medis", "billing"]

        def d(billing=True, dx2=(), age=3650):
            facts = [
                flag("history.prior_visit_same_dx"),
                flag("billing.has_therapy_beyond_consult", billing),
                flag("history.post_op_suture_removal", False),
                flag("procedure.odc_operatif", False),
            ]
            c = claim([("Z09.0", "primary")] + list(dx2), facts, enc="RJ", docs=docs)
            c["claim"]["patient"] = {"age_days": age}
            return c

        self.assertEqual(self.st("RJ-KONTROL_Z09_0", d()), "PASS")
        self.assertEqual(
            self.st("RJ-KONTROL_Z09_0", d(dx2=[("C50.9", "secondary")])), "FAIL"
        )
        self.assertEqual(self.st("RJ-KONTROL_Z09_0", d(age=5)), "FAIL")
        self.assertEqual(self.st("RJ-KONTROL_Z09_0", d(billing=False)), "FAIL")
        # data usia tidak ada -> REVIEW
        tanpa_usia = d()
        tanpa_usia["claim"]["patient"] = {}
        self.assertEqual(self.st("RJ-KONTROL_Z09_0", tanpa_usia), "REVIEW")

    # --- endoskopi & MRI (kode prosedur ICD-9-CM)
    def test_endoskopi_dan_mri(self):
        self.assertEqual(
            self.st(
                "RJ-ENDOSKOPI",
                claim(
                    [("J34.2", "primary")],
                    [cats("procedure.endoscopy_region", "hidung")],
                    enc="RJ",
                    procs=["21.21"],
                ),
            ),
            "PASS",
        )
        res = run(
            claim(
                [("J32.9", "primary")],
                [cats("procedure.endoscopy_region", "sinus")],
                enc="RJ",
                procs=["21.21"],
            )
        )
        r = next(x for x in res["results"] if x["rule_id"] == "RJ-ENDOSKOPI")
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(
            self.st(
                "RJ-ENDOSKOPI", claim([("J32.9", "primary")], enc="RJ", procs=["22.19"])
            ),
            "REVIEW",
        )
        self.assertEqual(
            self.st(
                "RJ-MRI",
                claim(
                    [("G93.9", "primary")],
                    [cats("procedure.mri_region", "otak")],
                    procs=["88.91"],
                ),
            ),
            "PASS",
        )
        self.assertEqual(
            self.st(
                "RJ-MRI",
                claim(
                    [("M54.5", "primary")],
                    [cats("procedure.mri_region", "tulang_belakang")],
                    procs=["88.91"],
                ),
            ),
            "FAIL",
        )

    # --- rehabilitasi
    def test_rehabilitasi(self):
        ok = claim(
            [("Z50.1", "primary")], [cats("therapy.rehabilitasi", "fisik")], enc="RJ"
        )
        self.assertEqual(self.st("RJ-REHABILITASI_Z50", ok), "PASS")
        salah = claim(
            [("Z50.1", "primary")], [cats("therapy.rehabilitasi", "wicara")], enc="RJ"
        )
        self.assertEqual(self.st("RJ-REHABILITASI_Z50", salah), "FAIL")
        tanpa = claim([("Z50.1", "primary")], enc="RJ")
        self.assertEqual(self.st("RJ-REHABILITASI_Z50", tanpa), "REVIEW")

    # --- anemia: pemilihan kode
    def test_anemia_kode_khusus(self):
        def sug(rid, doc):
            res = run(doc)
            r = next(x for x in res["results"] if x["rule_id"] == rid)
            return r["status"], r["suggest_codes"]

        self.assertEqual(
            sug(
                "RJ-ANEMIA_NEOPLASMA",
                claim([("D64.9", "secondary"), ("C34.9", "primary")], enc="RJ"),
            ),
            ("FAIL", ["D63.0"]),
        )
        self.assertEqual(
            sug(
                "RJ-ANEMIA_PENYAKIT_KRONIS",
                claim([("D64.9", "secondary"), ("N18.5", "primary")], enc="RJ"),
            ),
            ("FAIL", ["D63.8"]),
        )
        self.assertEqual(
            sug(
                "RJ-ANEMIA_PERDARAHAN",
                claim(
                    [("D64.9", "primary")], [flag("clinical.perdarahan_akut")], enc="RJ"
                ),
            )[0],
            "FAIL",
        )
        self.assertEqual(
            sug("RJ-ANEMIA_NEOPLASMA", claim([("D64.9", "primary")], enc="RJ"))[0],
            "PASS",
        )
        # tanpa data perdarahan -> REVIEW, bukan PASS
        self.assertEqual(
            sug("RJ-ANEMIA_PERDARAHAN", claim([("D64.9", "primary")], enc="RJ"))[0],
            "REVIEW",
        )

    # --- keloid
    def test_keloid(self):
        d = lambda v: claim(
            [("L91.0", "primary")],
            [flag("clinical.keloid_gangguan_fungsi", v)],
            enc="RJ",
            docs=["resume_medis"],
        )
        self.assertEqual(self.st("RJ-KELOID", d(True)), "PASS")
        res = run(d(False))
        r = next(x for x in res["results"] if x["rule_id"] == "RJ-KELOID")
        self.assertEqual((r["status"], r["actions"]), ("FAIL", ["suggest_remove"]))


class TestRuleSetLengkap(unittest.TestCase):
    def test_lint_tanpa_error(self):
        errors = [i for i in lint_rules(RULES, CATALOG) if i["level"] == "error"]
        self.assertEqual(errors, [])

    def test_jumlah_dan_status(self):
        from collections import Counter

        c = Counter(r["status"] for r in RULES["rules"])
        self.assertEqual(len(RULES["rules"]), 23)
        self.assertEqual(c["needs_clarification"], 2)  # sepsis, anemia RI
        self.assertEqual(c["draft"], 1)  # prosedur operasi

    def test_semua_aturan_punya_catatan_verifikasi(self):
        for r in RULES["rules"]:
            self.assertIn("verification_note", r["source"], r["id"])

    def test_semua_aturan_mencatat_lineage_dan_status_rekonsiliasi(self):
        lineage = RULES["ruleset"]["lineage"]
        self.assertEqual(
            lineage["upstream_document"],
            "docs/berita_acara_pending_klaim_tahun_2019.pdf",
        )
        self.assertEqual(lineage["intermediate_document"], "docs/rule_rsds.pdf")
        self.assertEqual(
            {r["source"]["reconciliation_status"] for r in RULES["rules"]},
            {"unverified", "disputed"},
        )
        self.assertTrue(
            all(r["source"].get("reconciliation_note") for r in RULES["rules"])
        )


class TestValidasiDokumenKlaim(unittest.TestCase):
    def test_contoh_klaim_valid(self):
        validate_claim_document(BASE)

    def test_jenis_layanan_tidak_dikenal_ditolak(self):
        doc = copy.deepcopy(BASE)
        doc["claim"]["encounter_type"] = "UGD"
        with self.assertRaisesRegex(ValueError, "encounter_type"):
            evaluate_claim(RULES, doc)

    def test_diagnosis_tanpa_posisi_valid_ditolak(self):
        doc = copy.deepcopy(BASE)
        del doc["claim"]["diagnoses"][0]["position"]
        with self.assertRaisesRegex(ValueError, "diagnoses\\[0\\].position"):
            validate_claim_document(doc)

    def test_status_fakta_tidak_dikenal_ditolak(self):
        doc = copy.deepcopy(BASE)
        doc["facts"][0]["status"] = "unknown"
        with self.assertRaisesRegex(ValueError, "facts\\[0\\].status"):
            validate_claim_document(doc)

    def test_provenance_fakta_tanpa_method_ditolak(self):
        doc = copy.deepcopy(BASE)
        doc["facts"][0]["provenance"] = {}
        with self.assertRaisesRegex(ValueError, "facts\\[0\\].provenance.method"):
            validate_claim_document(doc)


class TestHasilPerDiagnosis(unittest.TestCase):
    def test_hasil_mengikuti_urutan_diagnosis_tanpa_mutasi(self):
        doc = copy.deepcopy(BASE)
        original_diagnoses = copy.deepcopy(doc["claim"]["diagnoses"])

        result = evaluate_claim(approved_ruleset(), doc)

        diagnosis_results = result["diagnosis_results"]
        self.assertEqual(len(diagnosis_results), len(original_diagnoses))
        self.assertEqual(
            [item["diagnosis"] for item in diagnosis_results], original_diagnoses
        )
        self.assertEqual(
            [item["status"] for item in diagnosis_results],
            ["NOT_APPLICABLE", "PASS"],
        )
        self.assertEqual(doc["claim"]["diagnoses"], original_diagnoses)

    def test_scope_dan_posisi_membatasi_rule_diagnosis(self):
        facts = [
            fact("therapy.drugs", ["deferasirox"], kind="category_list"),
            fact("history.iron_chelation_claims_this_month", 1),
        ]
        documents = ["protokol_pemberian_kelasi_besi", "product_batch_obat"]
        primary = claim([("D56.1", "primary")], facts, enc="RJ", docs=documents)
        secondary = claim([("D56.1", "secondary")], facts, enc="RJ", docs=documents)
        inpatient = claim([("D56.1", "primary")], facts, enc="RI", docs=documents)

        self.assertEqual(
            evaluate_claim(approved_ruleset(), primary)["diagnosis_results"][0]["status"], "PASS"
        )
        self.assertEqual(
            evaluate_claim(approved_ruleset(), secondary)["diagnosis_results"][0]["status"],
            "NOT_APPLICABLE",
        )
        self.assertEqual(
            evaluate_claim(approved_ruleset(), inpatient)["diagnosis_results"][0]["status"],
            "NOT_APPLICABLE",
        )

    def test_rule_prosedur_tidak_mengubah_hasil_keseluruhan_diagnosis(self):
        procedure_only_claim = claim([], enc="RJ", procs=["21.21"])

        result = evaluate_claim(RULES, procedure_only_claim)

        self.assertEqual(result["diagnosis_results"], [])
        self.assertEqual(result["diagnosis_counts"], {})
        self.assertEqual(result["overall"], "NOT_APPLICABLE")


class TestProvenanceAturan(unittest.TestCase):
    LINEAGE = {
        "upstream_document": "Berita Acara Kesepakatan Pending Klaim",
        "intermediate_document": "rule_rsds.pdf",
        "schema_artifact": "rule_schema.json",
    }
    RULE = {
        "id": "ALL-DEMAM",
        "title": "Demam",
        "type": "clinical_validation",
        "scope": "ALL",
        "status": "active",
        "trigger": {"codes": ["J18.9"]},
        "evidence": {"field": "symptom.demam", "op": "eq", "value": True},
        "outcome": {"pass_message": "Sesuai", "fail_message": "Tidak sesuai"},
        "source": {
            "document": "BA Kesepakatan Pending Klaim",
            "year": 2019,
            "reference": "halaman 3",
            "origin_note": "rule_rsds.pdf, bagian pneumonia",
            "verified_against_original": True,
            "reconciliation_status": "verified",
            "reconciliation_note": "Cocok dengan kedua sumber.",
        },
    }

    def evaluate(self, rule, options=None):
        claim_doc = claim(
            [("J18.9", "primary")], [fact("symptom.demam", True, kind="flag")]
        )
        return evaluate_claim(
            {"ruleset": {"lineage": self.LINEAGE}, "rules": [rule]}, claim_doc, options
        )["results"][0]

    def test_hanya_rule_verified_dapat_memberikan_keputusan_final(self):
        self.assertEqual(self.evaluate(copy.deepcopy(self.RULE))["status"], "PASS")

        excluded = self.evaluate(copy.deepcopy(self.RULE), Options(include_statuses=()))
        self.assertEqual(excluded["status"], "REVIEW")

        unverified = copy.deepcopy(self.RULE)
        unverified["source"]["verified_against_original"] = False
        unverified["source"]["reconciliation_status"] = "unverified"
        self.assertEqual(self.evaluate(unverified)["status"], "REVIEW")

        legacy = copy.deepcopy(self.RULE)
        del legacy["source"]["reconciliation_status"]
        self.assertEqual(self.evaluate(legacy)["status"], "REVIEW")

        disputed = copy.deepcopy(self.RULE)
        disputed["source"]["reconciliation_status"] = "disputed"
        self.assertEqual(self.evaluate(disputed)["status"], "REVIEW")

        draft = copy.deepcopy(self.RULE)
        draft["status"] = "draft"
        draft["source"]["reconciliation_status"] = "unverified"
        self.assertEqual(self.evaluate(draft)["status"], "REVIEW")

    def test_hasil_menampilkan_sumber_dan_lineage(self):
        result = self.evaluate(copy.deepcopy(self.RULE))
        self.assertEqual(
            result["source_details"]["document"], "BA Kesepakatan Pending Klaim"
        )
        self.assertEqual(result["source_details"]["year"], 2019)
        self.assertEqual(result["source_details"]["reference"], "halaman 3")
        self.assertEqual(
            result["source_details"]["lineage"]["intermediate_document"],
            "rule_rsds.pdf",
        )

    def test_rule_disputed_dalam_data_produksi_hanya_menghasilkan_review(self):
        result = evaluate_claim(
            RULES,
            claim(
                [("E87.6", "secondary")],
                [
                    fact("lab.kalium", 2.6),
                    fact("therapy.drugs", ["kcl_injeksi"], kind="category_list"),
                ],
                docs=["hasil_lab", "resume_medis"],
            ),
        )["diagnosis_results"][0]
        self.assertEqual(result["status"], "REVIEW")
        rule_result = result["rule_results"][0]
        self.assertEqual(rule_result["source_details"]["reconciliation_status"], "disputed")
        self.assertEqual(
            rule_result["source_details"]["lineage"]["upstream_document"],
            "docs/berita_acara_pending_klaim_tahun_2019.pdf",
        )


if __name__ == "__main__":
    unittest.main()
