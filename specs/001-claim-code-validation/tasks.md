# Tasks: Claim Diagnosis Code Validation

**Input**: Design documents from `/specs/001-claim-code-validation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Included because the specification defines independent acceptance tests and the project constitution requires behavior-focused automated tests.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated as an increment.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Formalize the claim input contract used by the shared evaluator.

- [X] T001 Add `claim_facts_schema.json` under `src/pending_klaim_rule_engine/` for claim encounter type, ordered diagnosis entries, supporting facts, document availability, and provenance; make direct patient identifiers optional and unnecessary for evaluation.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Enforce the input boundary before any user-story evaluation.

- [X] T002 Implement claim/fact shape validation in `src/pending_klaim_rule_engine/klaim_engine.py` and call it before evaluation; reject unknown encounter types, malformed diagnosis entries, unsupported diagnosis positions, and malformed fact status/provenance with actionable errors.

**Checkpoint**: Claim inputs have a defined contract and are validated before rule evaluation.

---

## Phase 3: User Story 1 - Periksa kode diagnosis klaim (Priority: P1) - MVP

**Goal**: Evaluate each entered diagnosis against only matching rules and preserve the submitted codes and ordering.

**Independent Test**: Evaluate sample RI and RJ claims containing primary and secondary diagnoses, a position-restricted rule, and a code with no applicable rule. Confirm each input diagnosis has its own status/reason and the input diagnosis list is unchanged.

- [X] T003 [US1] Add tests in `src/pending_klaim_rule_engine/test_klaim_engine.py` for RI/RJ scope matching, primary/secondary position matching, unmatched diagnoses returning `NOT_APPLICABLE`, one result per diagnosis, and unchanged diagnosis codes/order.
- [X] T004 [US1] Update `evaluate_claim()` and rule applicability in `src/pending_klaim_rule_engine/klaim_engine.py` to produce a result for each diagnosis, evaluate only its matching code/scope/position rules, retain `NOT_APPLICABLE` when no diagnosis rule applies, and never mutate diagnosis input.
- [X] T005 [P] [US1] Expose the existing CLI `main()` through `src/pending_klaim_rule_engine/__init__.py` so the `pending-klaim-rule-engine` entry point declared in `pyproject.toml` is runnable.

**Checkpoint**: A verifier can run a claim through the package CLI and inspect independent results without diagnosis edits.

---

## Phase 4: User Story 2 - Pahami bukti dan tindak lanjut (Priority: P2)

**Goal**: Make missing, conflicting, and supporting evidence understandable and actionable for each diagnosis result.

**Independent Test**: Evaluate claims with a missing required fact, a missing required document, and conflicting facts from two sources. Confirm each result is `REVIEW` where appropriate and exposes missing items, both source values/provenance, the criteria trace, and a next step.

- [X] T006 [US2] Add tests in `src/pending_klaim_rule_engine/test_klaim_engine.py` for missing facts, missing documents, conflicting values from distinct sources, and traceable suggested actions; assert conflicts never produce a final status.
- [X] T007 [US2] Extend evidence trace and result construction in `src/pending_klaim_rule_engine/klaim_engine.py` and document the output in `specs/001-claim-code-validation/contracts/README.md` to show all conflicting values and provenance, identify missing fields/documents, and provide a next action while preserving the criterion-by-criterion trace.

**Checkpoint**: A verifier can identify why review is required and what evidence or action is needed.

---

## Phase 5: User Story 3 - Periksa dasar dan status aturan (Priority: P3)

**Goal**: Expose rule source lineage and ensure draft, unverified, or disputed rules cannot decide claims finally.

**Independent Test**: Evaluate one verified active diagnosis rule and one matching draft, unverified, or unresolved rule. Confirm source document/year/reference and verification details are returned, verified criteria can produce a final result, and unresolved rules produce `REVIEW` rather than `PASS` or `FAIL`.

- [X] T008 [US3] Add tests in `src/pending_klaim_rule_engine/test_klaim_engine.py` for verified active rules, unverified active rules, draft rules, and unresolved source differences; assert only verified and reconciled rules can produce `PASS` or `FAIL`.
- [X] T009 [P] [US3] Extend ruleset metadata in `src/pending_klaim_rule_engine/rule_schema.json` with BA 2019 and RSDS lineage; extend each rule source definition with a reconciliation state distinguishing verified, unverified, and disputed interpretations.
- [X] T010 [P] [US3] Reconcile diagnosis rules in `src/pending_klaim_rule_engine/rules_ba_2019.json` against `docs/rule_rsds.pdf` and `docs/berita_acara_pending_klaim_tahun_2019.pdf`; record source year/reference and lineage, and mark rules unverified or disputed unless they were checked against the cited source. Keep procedure-code rules outside the v1 diagnosis acceptance set.
- [X] T011 [US3] Update applicability and result formatting in `src/pending_klaim_rule_engine/klaim_engine.py` so a matching draft, unverified, or disputed rule yields `REVIEW`, while source document, year, page/section when known, verification state, and reconciliation note are visible in the diagnosis result.

**Checkpoint**: Rule decisions are traceable to their source chain and unresolved interpretations cannot yield final outcomes.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate all supported diagnosis cases and the documented end-to-end workflow.

- [ ] T012 Add table-driven acceptance cases in `src/pending_klaim_rule_engine/test_klaim_engine.py` for every diagnosis case in FR-008 across applicable service types, using examples approved by the coding/rule owner and covering expected `PASS`, `FAIL`, `REVIEW`, and `NOT_APPLICABLE` outcomes.

**Blocked**: T012 requires an acceptance claim set approved by the coding/rule owner. No such approved examples are present in the repository; do not infer clinical expected outcomes from the unverified/disputed rules.

- [X] T013 Run `uv run python -m unittest discover -s src/pending_klaim_rule_engine -p 'test_*.py'` and the rule lint command against `src/pending_klaim_rule_engine/rules_ba_2019.json` and `src/pending_klaim_rule_engine/field_catalog.json`; update expected commands/outcomes in `specs/001-claim-code-validation/quickstart.md` if they changed.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Defines the shared claim input schema; no code dependencies.
- **Foundational (Phase 2)**: Depends on T001 and blocks all user-story work.
- **User Stories (Phases 3-5)**: Depend on T002 and proceed in priority order for this single engine package.
- **Polish (Phase 6)**: Depends on the three user-story checkpoints and approved acceptance examples.

### User Story Dependencies

- **US1 (P1)**: Starts after T002; delivers the core per-diagnosis result workflow and is the MVP.
- **US2 (P2)**: Follows US1 because evidence explanations extend the per-diagnosis result contract.
- **US3 (P3)**: Follows US2 because source and reconciliation metadata are added to the shared result representation.

### Within Each User Story

- Add or update behavior-focused tests before implementation tasks.
- US1 T004 and T005 touch separate files and can proceed in parallel after T003.
- US3 T009 and T010 touch separate files and can proceed in parallel after T008; T011 depends on both artifacts.
- Other tasks are sequential where they share files or depend on newly established result behavior.

## Parallel Opportunities

- After US1 tests (T003), T004 (`klaim_engine.py`) and T005 (`__init__.py`) can run in parallel.
- After US3 tests (T008), T009 (`rule_schema.json`) and T010 (`rules_ba_2019.json`) can run in parallel, followed by T011.
- US2 and US3 are kept sequential in this plan because both change the shared evaluation result contract in `klaim_engine.py`.

## Implementation Strategy

### MVP First (User Story 1)

1. Complete T001-T002 for an explicit and validated claim input boundary.
2. Complete US1 tasks T003-T005.
3. Validate RI/RJ matching, diagnosis position, unmatched diagnosis behavior, input preservation, and the CLI entry point.
4. Deliver the core diagnosis checker before adding the richer evidence explanations and governance metadata.

### Incremental Delivery

1. Complete Setup and Foundational phases.
2. Deliver US1 as the usable MVP.
3. Add US2 evidence explanations and manual-review actions.
4. Add US3 source lineage and verification gating.
5. Complete cross-rule acceptance validation and the quickstart checks.
