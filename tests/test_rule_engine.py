from decimal import Decimal

import pytest

from pending_klaim_rule_engine.rule_engine import (
    E87_6_RULE,
    PositionEquals,
    RuleDefinition,
    RuleOutcome,
    evaluate_rule,
)


def test_e87_6_is_met_when_both_criteria_are_met():
    result = evaluate_rule(
        E87_6_RULE,
        {"potassium": Decimal("2.99"), "kcl_injection": True},
    )

    assert result.outcome is RuleOutcome.MET
    assert [criterion.outcome for criterion in result.criteria] == [
        RuleOutcome.MET,
        RuleOutcome.MET,
    ]


@pytest.mark.parametrize(
    ("evidence", "unmet_criterion"),
    [
        ({"potassium": Decimal("3.01"), "kcl_injection": True}, "potassium_below_3_00"),
        ({"potassium": Decimal("2.99"), "kcl_injection": False}, "kcl_injection"),
    ],
)
def test_e87_6_is_not_met_when_either_criterion_is_not_met(evidence, unmet_criterion):
    result = evaluate_rule(E87_6_RULE, evidence)

    assert result.outcome is RuleOutcome.NOT_MET
    assert next(
        criterion.outcome
        for criterion in result.criteria
        if criterion.criterion_id == unmet_criterion
    ) is RuleOutcome.NOT_MET


def test_e87_6_boundary_value_of_3_is_not_below_threshold():
    result = evaluate_rule(
        E87_6_RULE,
        {"potassium": Decimal("3.00"), "kcl_injection": True},
    )

    assert result.outcome is RuleOutcome.NOT_MET


@pytest.mark.parametrize(
    "evidence",
    [
        {"kcl_injection": True},
        {"potassium": Decimal("2.99")},
        {},
    ],
)
def test_e87_6_reports_missing_criteria_as_evidence_not_found(evidence):
    result = evaluate_rule(E87_6_RULE, evidence)

    assert result.outcome is RuleOutcome.EVIDENCE_NOT_FOUND


def test_e87_6_does_not_check_diagnosis_position():
    result = evaluate_rule(
        E87_6_RULE,
        {
            "potassium": Decimal("2.99"),
            "kcl_injection": True,
            "diagnosis_position": "primary",
        },
    )

    assert result.outcome is RuleOutcome.MET
    assert [criterion.criterion_id for criterion in result.criteria] == [
        "potassium_below_3_00",
        "kcl_injection",
    ]


@pytest.mark.parametrize(
    ("position", "expected"),
    [("secondary", RuleOutcome.MET), ("primary", RuleOutcome.NOT_MET)],
)
def test_rule_checks_position_when_criterion_is_declared(position, expected):
    rule = RuleDefinition(
        code="SYNTHETIC",
        name="Synthetic secondary diagnosis rule",
        criteria=(
            PositionEquals(
                id="secondary_position",
                description="Diagnosis must be secondary",
                evidence_key="diagnosis_position",
                expected_position="secondary",
            ),
        ),
    )

    result = evaluate_rule(rule, {"diagnosis_position": position})

    assert result.outcome is expected