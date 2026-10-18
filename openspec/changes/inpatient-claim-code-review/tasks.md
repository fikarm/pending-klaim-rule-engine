# Tasks

**Implementation requirements:** For every Python function, method, or class introduced or modified by a task, add type hints where applicable and a concise docstring describing its purpose or contract. Whenever a task introduces or modifies a complex or non-obvious logic path, add a concise inline code comment explaining its rationale or behavior. Include verification of these requirements in the task's completion check; do not add comments that merely narrate straightforward code.

## 1. Rule Evaluation Foundation

- [x] 1.1 Add the project's test setup and a repeatable test command; verify the test runner executes a baseline test successfully.
- [x] 1.2 Implement declarative rule criteria and the E87.6 evaluator for potassium < 3.00 AND documented KCl injection; verify tests for both met, either unmet, boundary value, and missing evidence.
- [x] 1.3 Implement criterion-level outcomes and optional diagnosis-position evaluation; verify E87.6 omits position while a synthetic rule with an explicit position criterion checks it.

## 2. PostgreSQL Persistence and Rule Lifecycle

- [ ] 2.1 Define and migrate PostgreSQL persistence for source references, rule identities and immutable versions, evidence, and evaluations; type-hint and document any new or modified Python migration or integrity helpers, add concise inline comments for complex logic, and verify migrations apply, integration tests round-trip these records, and the annotations and comments explain the relevant contracts and decisions.
- [x] 2.2 Implement draft, reviewed, and active rule transitions with source provenance; verify only reviewed active versions can be activated and used for new evaluations.
- [x] 2.3 Preserve rule-version references on evaluations after a revision; verify an earlier evaluation still displays its original rule version after a newer version is activated.

## 3. Structured Claim Review

- [x] 3.1 Implement structured entry for the diagnosis under review, potassium result, KCl injection evidence, and evidence references; verify valid input is accepted and missing required input is represented as evidence not found.
- [ ] 3.2 Connect submitted evidence to the active rule evaluator and persist criterion outcomes with evidence and rule-version references; type-hint and document each new or modified Python function or class, add concise inline comments for complex rule-selection, missing-evidence, or outcome-persistence logic, and verify an end-to-end E87.6 review against PostgreSQL plus review the annotations, docstrings, and comments.
- [x] 3.3 Present outcomes as met, not met, or evidence not found without deciding claim acceptance or rejection; verify each outcome is visible with its criterion and source references.
- [x] 3.4 Add synthetic E87.6 examples and document how to run the structured review and tests; verify the documented development workflow succeeds without real patient data.

## 4. Integration Verification

- [ ] 4.1 Run the complete test suite against PostgreSQL and verify a synthetic review remains reproducible against the exact rule version used; for any Python code changed to resolve integration failures, verify type hints and docstrings are present and add and review concise inline comments for complex integration logic.