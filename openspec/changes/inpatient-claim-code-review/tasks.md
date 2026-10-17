# Tasks

## 1. Rule Evaluation Foundation

- [ ] 1.1 Add the project's test setup and a repeatable test command; verify the test runner executes a baseline test successfully.
- [ ] 1.2 Implement declarative rule criteria and the E87.6 evaluator for potassium < 3.00 AND documented KCl injection; verify tests for both met, either unmet, boundary value, and missing evidence.
- [ ] 1.3 Implement criterion-level outcomes and optional diagnosis-position evaluation; verify E87.6 omits position while a synthetic rule with an explicit position criterion checks it.

## 2. PostgreSQL Persistence and Rule Lifecycle

- [ ] 2.1 Define and migrate PostgreSQL persistence for source references, rule identities and immutable versions, evidence, and evaluations; verify migrations apply and integration tests round-trip these records.
- [ ] 2.2 Implement draft, reviewed, and active rule transitions with source provenance; verify only reviewed active versions can be activated and used for new evaluations.
- [ ] 2.3 Preserve rule-version references on evaluations after a revision; verify an earlier evaluation still displays its original rule version after a newer version is activated.

## 3. Structured Claim Review

- [ ] 3.1 Implement structured entry for the diagnosis under review, potassium result, KCl injection evidence, and evidence references; verify valid input is accepted and missing required input is represented as evidence not found.
- [ ] 3.2 Connect submitted evidence to the active rule evaluator and persist criterion outcomes with evidence and rule-version references; verify an end-to-end E87.6 review against PostgreSQL.
- [ ] 3.3 Present outcomes as met, not met, or evidence not found without deciding claim acceptance or rejection; verify each outcome is visible with its criterion and source references.
- [ ] 3.4 Add synthetic E87.6 examples and document how to run the structured review and tests; verify the documented development workflow succeeds without real patient data.

## 4. Integration Verification

- [ ] 4.1 Run the complete test suite against PostgreSQL and verify a synthetic review remains reproducible against the exact rule version used.