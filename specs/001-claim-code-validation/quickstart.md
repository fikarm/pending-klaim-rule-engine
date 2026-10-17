# Quickstart Validation Guide

## Goal

Validate a claim against the rule set and confirm that each diagnosis receives a deterministic status with traceable evidence.

## Prerequisites

- Python 3.14 or compatible interpreter
- Repository dependencies already managed in the project environment
- Access to the example rules and sample claim data in the repository

## Setup

```bash
cd /media/fikarm/shared/projects/pending-klaim-rule-engine
uv sync
```

## Run the example evaluation

```bash
uv run python -m pending_klaim_rule_engine.klaim_engine \
  evaluate \
  --rules src/pending_klaim_rule_engine/rules_ba_2019.json \
  --facts src/pending_klaim_rule_engine/claim_facts_example.json \
  --json
```

### Expected outcome

- The command returns a JSON payload with `overall`, per-rule `results`, and one ordered `diagnosis_results` entry per diagnosis.
- The supplied sample claim currently returns `REVIEW` for `E87.6` because that rule is marked disputed; this is intentional until the rule owner reconciles it against the BA and RSDS sources.
- Final `PASS` or `FAIL` results require active rules with verified source and reconciliation metadata and no unresolved questions.
- The response includes `derived_facts` when the engine derives values such as `pf_ratio` or `leukosit_tinggi`.

## Run the rule lint check

```bash
uv run python -m pending_klaim_rule_engine.klaim_engine \
  lint \
  --rules src/pending_klaim_rule_engine/rules_ba_2019.json \
  --catalog src/pending_klaim_rule_engine/field_catalog.json
```

### Expected outcome

- The lint command should return no errors for the current rule set.
- Warnings are expected for active rules that are unverified or have source interpretation questions; they require rule-owner review before final outcomes are enabled.

## Run the repository test suite

```bash
uv run python -m unittest discover -s src/pending_klaim_rule_engine -p 'test_*.py'
```

### Expected outcome

- The rule engine tests pass for representative valid, failed, review, and not-applicable cases.
- Focused checks include hipokalemia, respiratory failure, heart failure with hypertension, and thalassemia scenarios.

## Validation scenarios to inspect manually

1. A recognized primary diagnosis with sufficient supporting evidence and a verified, reconciled rule should result in `PASS`.
2. A diagnosis with missing mandatory documents should result in `REVIEW` or `FAIL` according to the configured policy, unless unresolved rule provenance independently requires `REVIEW`.
3. A diagnosis whose rule is outside scope or whose code does not match the trigger should result in `NOT_APPLICABLE`.
4. Conflicting evidence on a required field should result in `REVIEW` rather than a silent final decision.
