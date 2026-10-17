# Data Model: Claim Diagnosis Validation

## Overview

The validation domain centers on a single claim review transaction with diagnosis entries, supporting facts, and rule enforcement outputs. The engine intentionally separates claim input, rule definitions, and evaluation results so that the same rule set can be replayed deterministically.

## Core Entities

### ClaimContext

Represents one claim review session.

| Field | Type | Notes |
| --- | --- | --- |
| `claim_id` | string | Stable identifier of the claim being reviewed |
| `encounter_type` | `RI` / `RJ` | Rawat inap or rawat jalan |
| `diagnoses` | array of `DiagnosisEntry` | Ordered list; order is preserved |
| `documents_available` | array of string | Supporting documents recorded for the claim |
| `facts` | array of `SupportingFact` | Clinical values and supporting evidence |
| `procedures` | array of `ProcedureEntry` | Optional for relevant rule triggers |
| `patient` | object | Patient metadata such as `age_days` if present |

### DiagnosisEntry

Represents one diagnosis in the claim.

| Field | Type | Notes |
| --- | --- | --- |
| `code` | string | ICD code, e.g. `E87.6`, `J96.0` |
| `position` | `primary` / `secondary` | Position within claim diagnosis ordering |

### SupportingFact

Represents a clinical fact or piece of evidence.

| Field | Type | Notes |
| --- | --- | --- |
| `field` | string | Field path, e.g. `lab.kalium`, `vital.spo2` |
| `status` | `present` / `absent` / `conflicting` | Evidence state |
| `kind` | string | `measurement`, `category`, `flag`, `category_list` |
| `value` | any | Actual fact value |
| `unit` | string or null | Unit, if relevant |
| `observed_at` | string or null | ISO timestamp |
| `provenance` | object | Source and metadata |
| `confidence` | number or null | Optional confidence score for extraction |

### RuleDefinition

Represents one validation rule.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Unique rule identifier, e.g. `RI-HIPOKALEMIA` |
| `title` | string | Human-readable title |
| `type` | string | `clinical_validation`, `code_selection`, `administrative` |
| `scope` | `RI` / `RJ` / `ALL` | Service scope |
| `status` | `active` / `draft` / `needs_clarification` / `deprecated` | Production eligibility |
| `trigger` | object | Code pattern and diagnosis position |
| `evidence` | `Node` | Positive evidence requirements |
| `treatment` | `Node` | Treatment/management checks |
| `extra_conditions` | `Node` | Additional qualifiers |
| `violation_when` | `Node` | Inverse or negative condition |
| `required_documents` | array of string | Mandatory documents |
| `source` | object | Reference document, original-source verification, and reconciliation status (`verified`, `unverified`, `disputed`) |
| `outcome` | object | Pass/fail/review messages and suggested actions |

### RuleSetLineage

Ruleset-level provenance records the derivation chain shared by the rule data.

| Field | Type | Notes |
| --- | --- | --- |
| `upstream_document` | string | BA 2019 PDF path |
| `intermediate_document` | string | RSDS-derived rules PDF path |
| `schema_artifact` | string | JSON rule schema path |
| `rule_artifact` | string | JSON ruleset path |

### RuleEvaluationResult

The result emitted for one diagnosis-rule pair.

| Field | Type | Notes |
| --- | --- | --- |
| `rule_id` | string | Matching rule |
| `status` | `PASS` / `FAIL` / `REVIEW` / `NOT_APPLICABLE` | Final result |
| `message` | string | Human-readable explanation |
| `matched_codes` | array of string | Trigger codes that matched |
| `missing_documents` | array of string | Required but absent documents |
| `missing_fields` | array of string | Evidence fields not documented or below the confidence threshold |
| `suggest_codes` | array of string | Recommended substitutions for code-selection rules |
| `actions` | array of string | Suggested next steps |
| `trace` | object | Node-by-node analysis details |
| `source` | string | Rule source label |
| `verified_against_original` | boolean | Whether the rule has been checked against the source |
| `source_details` | object | Source metadata plus ruleset lineage and reconciliation note |

### DiagnosisEvaluationResult

Represents the ordered aggregate result for one claim diagnosis.

| Field | Type | Notes |
| --- | --- | --- |
| `diagnosis_index` | integer | Zero-based index in the original diagnosis list |
| `diagnosis` | `DiagnosisEntry` | Original entry; never rewritten |
| `status` | `PASS` / `FAIL` / `REVIEW` / `NOT_APPLICABLE` | Aggregate status of matching diagnosis rules |
| `message` | string | Summary reason |
| `rule_results` | array of `RuleEvaluationResult` | Matching rules for this diagnosis |

## Relationships

- One `ClaimContext` contains many `DiagnosisEntry` records.
- One `DiagnosisEntry` can match many rule triggers depending on code and position.
- Many `SupportingFact` records support one or many rule evaluations.
- Each `RuleDefinition` produces at most one `RuleEvaluationResult` for a claim/diagnosis evaluation.
- Each claim diagnosis produces exactly one ordered `DiagnosisEvaluationResult`; ICD-9-CM procedure rules are not included in this v1 diagnosis summary.
- `RuleEvaluationResult` is derived by evaluating logical `Node` expressions over the supporting facts in the claim.

## Validation Rules and Behavior

### Claim-level constraints

- `encounter_type` must be one of `RI` or `RJ`.
- Diagnosis ordering is preserved and never rewritten by the engine.
- If no rule matches the trigger code, the result is `NOT_APPLICABLE`.

### Fact-level constraints

- The engine distinguishes `present`, `absent`, and `conflicting` states.
- `unit` mismatches are treated as `REVIEW` when they may affect the interpretation.
- Low-confidence LLM extraction is ignored unless the confidence threshold is met.

### Rule status constraints

- Only rules with `status: active` are included in the default production evaluation set.
- A final `PASS` or `FAIL` requires an active rule, `verified_against_original: true`, `reconciliation_status: verified`, and no unresolved `open_questions`.
- A matching draft, unverified, disputed, legacy rule without reconciliation metadata, or rule with open questions yields `REVIEW`.

## State Transitions

### Evidence states

`present` -> evaluated as a positive or negative condition depending on operator.
`absent` -> considered missing but explicit; may yield a fail if the condition requires presence.
`conflicting` -> renders the evaluation `REVIEW` unless the rule has a clear override.

### Rule outcome states

`NOT_APPLICABLE` when no rule matches the claim and service context.
`PASS` when all applicable criteria succeed and required documents are available.
`FAIL` when a rule is applicable and a condition fails or a required document is missing under fail policy.
`REVIEW` when evidence is incomplete, conflicting, or the rule is not verified.

## Derived Data Handling

The engine may append derived facts such as:
- `bga.pf_ratio`
- `bga.pco2_delta_from_baseline`
- `lab.leukosit_tinggi`

These values are annotated with provenance so that audit trails remain traceable.
