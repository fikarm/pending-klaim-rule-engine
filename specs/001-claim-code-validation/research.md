# Research: Claim Diagnosis Validation

## Decision Summary

- The feature will remain a deterministic, local-only rule engine implemented in Python without external services or LLM calls.
- Validation is performed per diagnosis against rules filtered by encounter type, diagnosis position, and trigger code.
- The engine treats missing or conflicting evidence as non-final states and defaults to `REVIEW` rather than silently forcing a pass/fail decision.
- The repository's JSON schema, field catalog, and rule set define the implementation contracts, but they are derived artifacts rather than the ultimate source of policy.

## Rationale

The specification is already consistent with a pure rules-engine approach. The repository contains a schema, field catalog, and sample claims/rules that encode enforcement semantics and evidence handling. This is a better fit than a freeform model-based approach because the constitution requires determinism, auditability, and reviewable outcomes.

## Research Findings

### 1. Rule source lineage and change propagation

The rule artifacts follow this source chain:

`docs/berita_acara_pending_klaim_tahun_2019.pdf` -> `docs/rule_rsds.pdf` -> `src/pending_klaim_rule_engine/rule_schema.json` and the corresponding JSON rule set.

The BA is the upstream reference, while the RSDS document is an intermediate interpretation. The schema and rules may need to change when the RSDS rules change. Updates must therefore be traced through this chain, checked against both source documents, and reviewed for unresolved differences; a downstream JSON change alone does not establish that a rule is verified against the original BA.

### 2. Rule applicability and evidence model

The engine evaluates each rule only when:
- the rule status is included in the active set (`active` by default),
- encounter type matches the rule scope (`RI`, `RJ`, or `ALL`),
- the rule's trigger code patterns match the diagnosis codes on the claim, and
- the diagnosis position matches the configured trigger position when supplied.

This creates a stable evaluation boundary that prevents unrelated rules from affecting a diagnosis result.

### 3. Three-valued logic for uncertain evidence

The project uses Kleene logic with `True`, `False`, and `None` (`U` for unknown). This is explicitly intended to distinguish:
- confirmed positive evidence,
- confirmed negative evidence,
- missing or conflicting evidence.

The engine converts missing, low-confidence, or conflicting facts into `REVIEW` unless a policy explicitly chooses to fail the rule. This matches the acceptance criteria for manual review when evidence is incomplete.

### 4. Output contract and traceability

Each evaluation result includes:
- the rule identifier and title,
- the applicable source reference and verification status,
- the matched diagnosis codes,
- the rule message,
- missing document requirements,
- suggested actions, and
- a trace object with node-by-node evaluation details.

This provides an audit trail that aligns with the constitution and the requirement to explain why a result was final or non-final.

### 5. Rule quality guardrails

The engine provides a `lint_rules` pass that validates:
- schema structure,
- operator compatibility for each field kind,
- unknown field references,
- invalid document types,
- unit mismatches,
- allowed-values mismatches, and
- duplicate rule IDs.

This is the mechanism that keeps production rules aligned with the field catalog and prevents silent drift.

## Alternatives Considered

### A. Hardcoded special-case logic for each diagnosis

Rejected because it would duplicate the rule catalog and make maintenance difficult. The rules and field catalog are already designed to describe the logic declaratively.

### B. Treating missing evidence as automatic failure

Rejected because the requirement explicitly says missing or conflicting evidence should become `REVIEW` unless the verifier intentionally selects a stricter policy. The engine already supports a configurable `missing_document_policy` with `review` as the default.

### C. Relying on external data services or model inference

Rejected because the constitution requires deterministic, auditable evaluation unaffected by network or hidden state. The project is intentionally offline and standard-library based.

## Open Questions Resolved

- The project type is a deterministic Python library/CLI engine, not a web service.
- The evaluation target is diagnosis-code validation for inpatient/outpatient claims.
- The policy source lineage is BA 2019 -> RSDS rules -> JSON schema/rules; JSON artifacts implement the derived rules and must remain traceable to that lineage.
- Evidence gaps and source conflicts are handled as `REVIEW` states, not silent pass/fail decisions.
