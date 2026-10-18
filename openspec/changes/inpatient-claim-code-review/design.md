# Design

## Context

See proposal.md for motivation and the spec deltas for user-visible behavior. The repository is currently a Python package skeleton with no persistence or application layers. The operational rule source is the RSDS interpretation PDF; the Ministry agreement is its source reference, and the scanned original requires page-level human verification before rules are activated.

## Goals / Non-Goals

**Goals:**
- Keep rule criteria reviewable, versioned, and independent from evaluation code.
- Make each evaluation reproducible against an immutable rule version and its evidence.
- Support the E87.6 pilot with structured numeric and treatment evidence.

**Non-Goals:**
- Automatically extracting clinical facts from PDFs or making claim adjudication decisions.
- General-purpose authoring of arbitrary executable rules.
- Defining production identity-provider integration or clinical-data retention policy in this pilot.

## Decisions

### Represent rules as declarative, versioned data

Store each rule version as structured data containing the diagnosis code, applicability, criteria, criterion-combination operator, optional diagnosis-position criterion, operational source, and source references. Criteria use a constrained vocabulary such as numeric threshold and treatment presence; the E87.6 pilot uses potassium `< 3.00` AND KCl injection present. Do not evaluate user-authored code or natural-language instructions as executable logic.

Alternative considered: hard-code each diagnosis in Python. This is simple for E87.6 but makes RSDS revisions require code changes and obscures rule provenance, so it is not the default.

### Separate source documents, operational rule versions, and evaluations

Use PostgreSQL records for source documents, rule identities and versions, review/evaluation records, entered evidence, and per-criterion outcomes. An evaluation references one immutable active rule version. Store the RSDS interpretation as the operational source and separately record its cited official source, page/section, and verification state; do not imply that RSDS interpretation is itself a Ministry rule.

Alternative considered: keep rule definitions only in application configuration. That makes revision history, approval workflow, and evaluation reproducibility harder to enforce.

### Evaluate only explicit criteria and preserve three-valued outcomes

The evaluator applies the declared AND/OR relationship and reports each criterion as met, not met, or evidence not found. A missing value is not treated as a negative clinical finding. Diagnosis position is evaluated only when the selected rule version declares a position criterion; otherwise it is omitted from the evaluation.

### Keep review input explicit and human-verifiable

For E87.6, collect potassium value, unit and relevant evidence reference, plus whether KCl injection is documented and its evidence reference. A reviewer enters or confirms these values through the structured form. The evaluation output presents criterion-level results and rule/source references for reviewer judgment.

### Activate revisions without rewriting past evaluations

Rule edits create a new draft version. A reviewer can mark it reviewed and an authorized user activates it; only active versions are used for new evaluations. Past evaluations retain their original rule-version reference. The identity and authorization mechanism for authorized users is an integration decision for deployment.

### Use typed and documented Python interfaces

Every Python function, method, or class introduced or modified by the remaining tasks must use type hints where applicable and concise docstrings that describe its purpose or contract. Add inline comments only for complex or non-obvious control flow, invariants, and persistence decisions; avoid comments that merely narrate straightforward code. This keeps the implementation maintainable without requiring a retrofit of already completed work.

Alternative considered: annotate and document the entire existing package. That would expand this change beyond its remaining implementation tasks without improving the specified review behavior.

## Risks / Trade-offs

- [The scanned official PDF may be misread during OCR] -> Require human verification of cited pages and criteria before a rule can be activated.
- [A constrained criterion vocabulary may not express future RSDS rules] -> Add explicitly typed criterion kinds as new rules require them; do not fall back to executable free text.
- [Structured manual entry can omit or mistype evidence] -> Require evidence references and show entered values alongside each criterion outcome for reviewer confirmation.
- [Clinical data in PostgreSQL may be sensitive] -> Use synthetic data in development; determine production access controls, audit policy, and retention before loading real claims.

## Migration Plan

There is no existing application data to migrate. Create the initial PostgreSQL schema and load only a verified E87.6 draft rule with synthetic review examples. Validate its source references and expected outcomes, then activate the rule through the review workflow. Roll back a faulty rule by deactivating the new version and reactivating the prior version; do not rewrite evaluations already completed.

## Open Questions

- Which authentication or identity service will identify reviewers and authorized rule approvers in the eventual deployment?
- What production access-control, audit, and retention policies apply to claim evidence?