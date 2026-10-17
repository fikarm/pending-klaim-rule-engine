from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal, Mapping


class RuleOutcome(StrEnum):
    MET = "met"
    NOT_MET = "not_met"
    EVIDENCE_NOT_FOUND = "evidence_not_found"


@dataclass(frozen=True)
class NumericLessThan:
    id: str
    description: str
    evidence_key: str
    threshold: Decimal


@dataclass(frozen=True)
class TreatmentPresent:
    id: str
    description: str
    evidence_key: str


@dataclass(frozen=True)
class PositionEquals:
    id: str
    description: str
    evidence_key: str
    expected_position: Literal["primary", "secondary"]


Criterion = NumericLessThan | TreatmentPresent | PositionEquals


@dataclass(frozen=True)
class RuleDefinition:
    code: str
    name: str
    criteria: tuple[Criterion, ...]
    operator: Literal["all", "any"] = "all"

    def __post_init__(self) -> None:
        if not self.criteria:
            raise ValueError("A rule must define at least one criterion")
        criterion_ids = [criterion.id for criterion in self.criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("Criterion IDs must be unique within a rule")


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    description: str
    outcome: RuleOutcome


@dataclass(frozen=True)
class RuleEvaluation:
    code: str
    outcome: RuleOutcome
    criteria: tuple[CriterionResult, ...]


E87_6_RULE = RuleDefinition(
    code="E87.6",
    name="Hipokalemia",
    operator="all",
    criteria=(
        NumericLessThan(
            id="potassium_below_3_00",
            description="Nilai kalium < 3,00",
            evidence_key="potassium",
            threshold=Decimal("3.00"),
        ),
        TreatmentPresent(
            id="kcl_injection",
            description="Mendapat terapi injeksi KCl",
            evidence_key="kcl_injection",
        ),
    ),
)


def evaluate_rule(
    rule: RuleDefinition,
    evidence: Mapping[str, object],
) -> RuleEvaluation:
    results = tuple(_evaluate_criterion(criterion, evidence) for criterion in rule.criteria)
    outcomes = tuple(result.outcome for result in results)

    if rule.operator == "all":
        if RuleOutcome.NOT_MET in outcomes:
            outcome = RuleOutcome.NOT_MET
        elif RuleOutcome.EVIDENCE_NOT_FOUND in outcomes:
            outcome = RuleOutcome.EVIDENCE_NOT_FOUND
        else:
            outcome = RuleOutcome.MET
    else:
        if RuleOutcome.MET in outcomes:
            outcome = RuleOutcome.MET
        elif RuleOutcome.EVIDENCE_NOT_FOUND in outcomes:
            outcome = RuleOutcome.EVIDENCE_NOT_FOUND
        else:
            outcome = RuleOutcome.NOT_MET

    return RuleEvaluation(code=rule.code, outcome=outcome, criteria=results)


def _evaluate_criterion(
    criterion: Criterion,
    evidence: Mapping[str, object],
) -> CriterionResult:
    value = evidence.get(criterion.evidence_key)
    if value is None:
        outcome = RuleOutcome.EVIDENCE_NOT_FOUND
    elif isinstance(criterion, NumericLessThan):
        outcome = _evaluate_numeric_less_than(criterion, value)
    elif isinstance(criterion, TreatmentPresent):
        if not isinstance(value, bool):
            raise ValueError(f"Evidence '{criterion.evidence_key}' must be a boolean")
        outcome = RuleOutcome.MET if value else RuleOutcome.NOT_MET
    else:
        if value not in ("primary", "secondary"):
            raise ValueError(
                f"Evidence '{criterion.evidence_key}' must be a diagnosis position"
            )
        outcome = (
            RuleOutcome.MET
            if value == criterion.expected_position
            else RuleOutcome.NOT_MET
        )

    return CriterionResult(
        criterion_id=criterion.id,
        description=criterion.description,
        outcome=outcome,
    )


def _evaluate_numeric_less_than(
    criterion: NumericLessThan,
    value: object,
) -> RuleOutcome:
    if isinstance(value, bool):
        raise ValueError(f"Evidence '{criterion.evidence_key}' must be numeric")
    try:
        numeric_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(
            f"Evidence '{criterion.evidence_key}' must be numeric"
        ) from error
    if not numeric_value.is_finite():
        raise ValueError(f"Evidence '{criterion.evidence_key}' must be finite")
    return (
        RuleOutcome.MET
        if numeric_value < criterion.threshold
        else RuleOutcome.NOT_MET
    )