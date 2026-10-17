# Public Contracts

## 1. Rule set input contract

The repository uses a JSON schema defined in `src/pending_klaim_rule_engine/rule_schema.json`.

### Required top-level structure

```json
{
  "schema_version": "1.0",
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
        "verified_against_original": true
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
  "overall": "PASS",
  "counts": { "PASS": 1, "REVIEW": 0, "FAIL": 0 },
  "results": [
    {
      "rule_id": "RI-HIPOKALEMIA",
      "status": "PASS",
      "message": "...",
      "matched_codes": ["E87.6"],
      "missing_documents": [],
      "actions": ["flag"],
      "trace": {}
    }
  ],
  "derived_facts": [],
  "unverified_rules_used": []
}
```

## 4. CLI contract

```bash
python -m pending_klaim_rule_engine.klaim_engine evaluate \
  --rules <path-to-rules.json> \
  --facts <path-to-claim.json> \
  --include-statuses active \
  --json
```

This contract is intentionally local-only and designed for deterministic review, not for networked application processing.
