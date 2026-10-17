# Implementation Plan: Claim Diagnosis Code Validation

**Branch**: `001-claim-code-validation` | **Date**: 2026-10-17 | **Spec**: `/specs/001-claim-code-validation/spec.md`

**Input**: Feature specification from `/specs/001-claim-code-validation/spec.md`

## Summary

The project implements a deterministic Python rule engine for validating primary and secondary diagnosis codes against inpatient and outpatient claim rules. The design keeps the rule catalog, evaluation logic, and claim data separate while surfacing final statuses as `PASS`, `FAIL`, `REVIEW`, or `NOT_APPLICABLE` with required trace data for auditability.

## Technical Context

**Language/Version**: Python 3.14 (declared in `pyproject.toml`)

**Project Manager**: `uv` for dependency and environment management

**Primary Dependencies**: Standard library only; no runtime packages required

**Storage**: JSON files for claim facts, rules, and field metadata; no database layer in v1

**Testing**: `uv run python -m unittest discover -s src/pending_klaim_rule_engine -p 'test_*.py'`

**Target Platform**: Linux-based local CLI execution in the repository environment

**Project Type**: Python library/CLI engine for deterministic clinical validation

**Performance Goals**: Evaluate a single claim against the JSON rule set in memory with low latency and deterministic output

**Constraints**: Must remain offline, auditable, and deterministic; must preserve diagnosis order and not infer patient identity or claim submission actions

**Scale/Scope**: Single-claim rule validation across supported inpatient/outpatient diagnosis cases using JSON-defined rules and a field catalog

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Pass criteria checked against the constitution:

- Explicit Contracts and Code Quality: PASS — the repository defines `rule_schema.json`, `field_catalog.json`, and a concrete rule result model in the engine.
- Deterministic, Auditable Evaluation: PASS — no external APIs, no network calls, and every evaluation includes evidence trace and status explanation.
- Behavior-Focused Testing: PASS — tests cover PASS, FAIL, REVIEW, and NOT_APPLICABLE scenarios across representative rules and edge cases.
- Maintainable Boundaries: PASS — claim data, rule data, and business logic remain separated by domain modules and JSON assets.
- Reviewable, Regression-Safe Changes: PASS — the scope is intentionally limited and the core rule engine is covered by regression tests.

No constitution violations require a complexity exception.

## Project Structure

### Documentation (this feature)

```text
specs/001-claim-code-validation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
├── spec.md              # Feature specification
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
src/
├── pending_klaim_rule_engine/
│   ├── __init__.py
│   ├── claim_facts_example.json
│   ├── field_catalog.json
│   ├── klaim_engine.py
│   ├── rule_schema.json
│   ├── rules_ba_2019.json
│   └── test_klaim_engine.py
└── ...
```

**Structure Decision**: Single Python package with a CLI-style engine entry point and JSON-based rule/fact contracts. This matches the repository’s current architecture and the requirement for an auditable local validation flow.

## Complexity Tracking

No constitution violations were identified; no complexity exception is required.
