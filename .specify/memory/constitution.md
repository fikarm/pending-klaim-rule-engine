<!--
Sync Impact Report
Version change: Unversioned scaffold -> 1.0.0
Modified principles:
- Principle slot 1 -> I. Explicit Contracts and Code Quality
- Principle slot 2 -> II. Deterministic, Auditable Evaluation
- Principle slot 3 -> III. Behavior-Focused Testing
- Principle slot 4 -> IV. Maintainable Boundaries
- Principle slot 5 -> V. Reviewable, Regression-Safe Changes
Added sections: Technical Constraints; Development Workflow
Removed sections: None
Deferred TODOs: Original ratification date is unknown.
-->

# Pending Klaim Rule Engine Constitution

## Core Principles

### I. Explicit Contracts and Code Quality
The engine MUST define clear input, output, and error behavior for public interfaces and
structured data. Rule, fact, and claim fields MUST be validated at their boundaries; missing,
unknown, and invalid values MUST remain distinguishable. Changes MUST preserve the documented
contract or include an explicit migration path. This prevents accidental behavior changes in
claim decisions.

### II. Deterministic, Auditable Evaluation
Given the same rules, claim facts, and options, evaluation MUST produce the same statuses and
evidence. Evaluation logic MUST NOT depend on model calls, network access, or hidden mutable
state. Each decision MUST retain sufficient evidence and provenance to explain its result.
Determinism and traceability make outcomes reproducible and reviewable.

### III. Behavior-Focused Testing
Every behavior change MUST include or update automated tests that assert externally meaningful
results. Tests MUST cover relevant boundaries, missing or unknown data, and failure paths, not
only typical inputs. Rule and schema changes MUST be tested against representative valid and
invalid data. The complete test suite MUST pass before a change is considered ready.

### IV. Maintainable Boundaries
Evaluation logic, rule data, schema definitions, and command-line concerns MUST remain separated
by clear responsibilities. Functions and modules MUST stay cohesive; duplication or abstraction
MUST be introduced only when it reduces meaningful complexity. Names and structure MUST make
decision logic understandable without requiring knowledge of unrelated modules.

### V. Reviewable, Regression-Safe Changes
Changes MUST be scoped to a coherent behavior or maintenance goal and MUST avoid unrelated
refactoring. Reviews MUST consider correctness, test coverage, contract compatibility, and
maintainability. Any unavoidable breaking change MUST identify affected inputs or callers and
provide an explicit upgrade path.

## Technical Constraints

The package MUST support the Python versions declared in `pyproject.toml`. Runtime dependencies
MUST remain absent unless a dependency is justified by a concrete requirement and reviewed for
its maintenance and compatibility costs. Rule and claim data formats MUST be defined and checked
against the repository's schemas.

## Development Workflow

Before review, contributors MUST run the relevant tests and the complete test suite, and report
any checks that could not be run. Reviewers MUST verify that changes follow these principles,
that tests exercise the changed behavior, and that documentation or schemas are updated when
their contracts change.

## Governance
<!-- Example: Constitution supersedes all other practices; Amendments require documentation, approval, migration plan -->

Amendments MUST be proposed with their rationale and impact on existing principles, contracts,
and tests, and approved by project maintainers before adoption. The constitution is authoritative
for project engineering decisions; changes that conflict with it MUST either be revised or be
accompanied by an approved amendment. Maintainers MUST review compliance during code review and
identify justified exceptions explicitly.

Versioning follows semantic versioning: MAJOR for backward-incompatible governance or principle
changes, MINOR for new or materially expanded principles or sections, and PATCH for clarifications
that do not change obligations.

**Version**: 1.0.0 | **Ratified**: TODO(RATIFICATION_DATE): Original adoption date is unknown. | **Last Amended**: 2026-10-17
