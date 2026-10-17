from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from pending_klaim_rule_engine.models import (
    ClaimEvaluation,
    CriterionOutcomeRecord,
    EvaluationEvidence,
    RuleVersion,
)
from pending_klaim_rule_engine.review_form import StructuredClaimForm
from pending_klaim_rule_engine.rule_engine import (
    NumericLessThan,
    PositionEquals,
    RuleDefinition,
    RuleEvaluation,
    TreatmentPresent,
    evaluate_rule,
)
from pending_klaim_rule_engine.rule_lifecycle import get_active_rule_version


class NoActiveRuleError(LookupError):
    pass


OUTCOME_LABELS = {
    "met": "TERPENUHI",
    "not_met": "TIDAK TERPENUHI",
    "evidence_not_found": "BUKTI BELUM DITEMUKAN",
}


@dataclass(frozen=True)
class CriterionReview:
    criterion_id: str
    description: str
    outcome: str
    evidence_value: Any | None
    evidence_reference: str | None


@dataclass(frozen=True)
class ReviewReport:
    evaluation_id: int
    diagnosis_code: str
    diagnosis_position: str | None
    outcome: str
    rule_version_id: int
    rule_version_number: int
    criteria: tuple[CriterionReview, ...]
    operational_reference: str | None
    official_reference: str | None


def format_review_report(report: ReviewReport) -> str:
    lines = [
        f"Telaah diagnosis {report.diagnosis_code}",
        f"Status kriteria gabungan: {OUTCOME_LABELS[report.outcome]}",
        f"Versi rule: {report.rule_version_number}",
    ]
    if report.diagnosis_position is not None:
        lines.append(f"Posisi diagnosis: {report.diagnosis_position}")

    for criterion in report.criteria:
        lines.append(f"- {criterion.description}: {OUTCOME_LABELS[criterion.outcome]}")
        if criterion.evidence_value is not None:
            if isinstance(criterion.evidence_value, dict):
                value = criterion.evidence_value.get("value")
                unit = criterion.evidence_value.get("unit")
                rendered_value = f"{value} {unit}" if unit else str(value)
            else:
                rendered_value = str(criterion.evidence_value)
            lines.append(f"  Bukti: {rendered_value}")
        if criterion.evidence_reference:
            lines.append(f"  Rujukan bukti: {criterion.evidence_reference}")

    if report.operational_reference:
        lines.append(f"Rujukan rule RSDS: {report.operational_reference}")
    if report.official_reference:
        lines.append(f"Rujukan sumber resmi: {report.official_reference}")
    lines.append("Hasil ini mendukung telaah petugas, bukan keputusan penerimaan klaim.")
    return "\n".join(lines)


def serialize_rule(rule: RuleDefinition) -> list[dict[str, Any]]:
    criteria: list[dict[str, Any]] = []
    for criterion in rule.criteria:
        if isinstance(criterion, NumericLessThan):
            criteria.append(
                {
                    "type": "numeric_less_than",
                    "id": criterion.id,
                    "description": criterion.description,
                    "evidence_key": criterion.evidence_key,
                    "threshold": str(criterion.threshold),
                }
            )
        elif isinstance(criterion, TreatmentPresent):
            criteria.append(
                {
                    "type": "treatment_present",
                    "id": criterion.id,
                    "description": criterion.description,
                    "evidence_key": criterion.evidence_key,
                }
            )
        else:
            criteria.append(
                {
                    "type": "position_equals",
                    "id": criterion.id,
                    "description": criterion.description,
                    "evidence_key": criterion.evidence_key,
                    "expected_position": criterion.expected_position,
                }
            )
    return criteria


def evaluate_claim(
    session: Session,
    form: StructuredClaimForm,
) -> ReviewReport:
    version = get_active_rule_version(session, form.diagnosis_code)
    if version is None:
        raise NoActiveRuleError(
            f"No active rule is available for {form.diagnosis_code}"
        )

    rule = _deserialize_rule(form.diagnosis_code, version)
    evidence_values = form.evidence_values()
    if any(isinstance(criterion, PositionEquals) for criterion in rule.criteria):
        evidence_values["diagnosis_position"] = form.diagnosis_position
    result = evaluate_rule(rule, evidence_values)

    evaluation = ClaimEvaluation(
        rule_version_id=version.id,
        diagnosis_code=form.diagnosis_code,
        diagnosis_position=form.diagnosis_position,
        outcome=result.outcome.value,
    )
    session.add(evaluation)
    session.flush()

    criteria_by_id = {criterion.id: criterion for criterion in rule.criteria}
    values_by_key = form.evidence_values()
    references_by_key = form.evidence_references()
    report_criteria: list[CriterionReview] = []
    for criterion_result in result.criteria:
        criterion = criteria_by_id[criterion_result.criterion_id]
        evidence_value, stored_value = _evidence_for_criterion(
            criterion, form, values_by_key
        )
        evidence_reference = references_by_key.get(criterion.evidence_key)
        evidence_record = None
        if evidence_value is not None:
            evidence_record = EvaluationEvidence(
                evaluation_id=evaluation.id,
                criterion_id=criterion.id,
                evidence_key=criterion.evidence_key,
                value=stored_value,
                source_reference=evidence_reference,
            )
            session.add(evidence_record)
            session.flush()

        session.add(
            CriterionOutcomeRecord(
                evaluation_id=evaluation.id,
                criterion_id=criterion.id,
                outcome=criterion_result.outcome.value,
                evidence_id=evidence_record.id if evidence_record else None,
            )
        )
        report_criteria.append(
            CriterionReview(
                criterion_id=criterion.id,
                description=criterion.description,
                outcome=criterion_result.outcome.value,
                evidence_value=stored_value if evidence_record else None,
                evidence_reference=evidence_reference,
            )
        )

    session.flush()
    return ReviewReport(
        evaluation_id=evaluation.id,
        diagnosis_code=evaluation.diagnosis_code,
        diagnosis_position=evaluation.diagnosis_position,
        outcome=evaluation.outcome,
        rule_version_id=version.id,
        rule_version_number=version.version,
        criteria=tuple(report_criteria),
        operational_reference=version.operational_reference,
        official_reference=version.official_reference,
    )


def _deserialize_rule(code: str, version: RuleVersion) -> RuleDefinition:
    criteria = []
    for item in version.criteria:
        criterion_type = item["type"]
        if criterion_type == "numeric_less_than":
            criteria.append(
                NumericLessThan(
                    id=item["id"],
                    description=item["description"],
                    evidence_key=item["evidence_key"],
                    threshold=Decimal(item["threshold"]),
                )
            )
        elif criterion_type == "treatment_present":
            criteria.append(
                TreatmentPresent(
                    id=item["id"],
                    description=item["description"],
                    evidence_key=item["evidence_key"],
                )
            )
        elif criterion_type == "position_equals":
            criteria.append(
                PositionEquals(
                    id=item["id"],
                    description=item["description"],
                    evidence_key=item["evidence_key"],
                    expected_position=item["expected_position"],
                )
            )
        else:
            raise ValueError(f"Unsupported criterion type: {criterion_type}")
    return RuleDefinition(
        code=code,
        name=code,
        criteria=tuple(criteria),
        operator=version.operator,
    )


def _evidence_for_criterion(criterion, form, values_by_key):
    if isinstance(criterion, PositionEquals):
        value = form.diagnosis_position
        return value, value

    value = values_by_key.get(criterion.evidence_key)
    if value is None:
        return None, None
    if criterion.evidence_key == "potassium":
        return value, {
            "value": str(value),
            "unit": form.potassium_unit,
        }
    return value, value