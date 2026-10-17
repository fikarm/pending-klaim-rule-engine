# Public Contracts

## 1. Rule set input contract

The repository uses a JSON schema defined in `src/pending_klaim_rule_engine/rule_schema.json`.

### Required top-level structure

```json
{
  "schema_version": "1.0",
  "ruleset": {
    "lineage": {
      "upstream_document": "docs/berita_acara_pending_klaim_tahun_2019.pdf",
      "intermediate_document": "docs/rule_rsds.pdf",
      "schema_artifact": "src/pending_klaim_rule_engine/rule_schema.json",
      "rule_artifact": "src/pending_klaim_rule_engine/rules_ba_2019.json"
    }
  },
  "rules": [
    {
      "id": "RI-HIPOKALEMIA",
      "title": "Hipokalemia",
      "type": "clinical_validation",
      "scope": "RI",
      "status": "active",
      "trigger": {
        "codes": ["E87.6"],
        "position": "primary"
      },
      "evidence": { "field": "lab.kalium", "op": "lte", "value": 3.5 },
      "required_documents": ["hasil_lab", "resume_medis"],
      "outcome": {
        "pass_message": "Diagnosis sesuai dengan bukti klinis yang cukup.",
        "fail_message": "Diagnosis tidak sesuai dengan bukti klinis yang cukup.",
        "review_message": "Data belum cukup untuk keputusan final."
      },
      "source": {
        "document": "Berita Acara Pending Klaim",
        "year": 2019,
        "verified_against_original": true,
        "reconciliation_status": "verified",
        "reconciliation_note": "Sudah diperiksa terhadap BA dan dokumen RSDS."
      }
    }
  ]
}
```

## 2. Claim input contract

The evaluation engine expects a claim document shaped like the sample in `src/pending_klaim_rule_engine/claim_facts_example.json`.

### Required shape

```json
{
  "claim": {
    "claim_id": "T-001",
    "encounter_type": "RI",
    "diagnoses": [
      { "code": "E87.6", "position": "primary" }
    ],
    "documents_available": ["hasil_lab", "resume_medis"]
  },
  "facts": [
    {
      "field": "lab.kalium",
      "kind": "measurement",
      "status": "present",
      "value": 2.8,
      "unit": "mmol/L",
      "observed_at": "2026-09-02T08:00:00+07:00",
      "provenance": { "method": "db_query" }
    }
  ]
}
```

## 3. Output contract

The CLI `evaluate --json` command returns a deterministic document with the following major sections:

```json
{
  "claim_id": "T-001",
  "overall": "REVIEW",
  "counts": { "REVIEW": 1, "NOT_APPLICABLE": 22 },
  "diagnosis_counts": { "REVIEW": 1, "NOT_APPLICABLE": 1 },
  "results": [
    {
      "rule_id": "RI-HIPOKALEMIA",
      "status": "REVIEW",
      "message": "...",
      "matched_codes": ["E87.6"],
      "source_details": {
        "document": "Berita Acara Pending Klaim",
        "year": 2019,
        "reference": "halaman atau bagian jika diketahui",
        "verified_against_original": false,
        "reconciliation_status": "disputed",
        "lineage": {}
      },
      "missing_documents": [],
      "missing_fields": [],
      "actions": ["flag"],
      "trace": {}
    }
  ],
  "diagnosis_results": [
    {
      "diagnosis_index": 0,
      "diagnosis": { "code": "E87.6", "position": "primary" },
      "status": "REVIEW",
      "message": "Sedikitnya satu aturan diagnosis yang cocok memerlukan tinjauan manual.",
      "rule_results": ["hasil aturan yang cocok"]
    }
  ],
  "derived_facts": [],
  "unverified_rules_used": []
}
```

`diagnosis_results` contains exactly one ordered summary per diagnosis. Each summary contains the original diagnosis entry, aggregate status and message, and the matching per-rule results. Conflicting evidence in a trace preserves each source value and provenance; unknown evidence is identified in `missing_fields` and produces a `manual_review` action.

`overall` and `diagnosis_counts` summarize diagnosis results only. `counts` summarizes the legacy flat per-rule `results` array, which can include non-diagnosis rules; those rules do not affect the diagnosis-level `overall` status.

## 4. CLI contract

```bash
python -m pending_klaim_rule_engine.klaim_engine evaluate \
  --rules <path-to-rules.json> \
  --facts <path-to-claim.json> \
  --include-statuses active \
  --json
```

This contract is intentionally local-only and designed for deterministic review, not for networked application processing.
