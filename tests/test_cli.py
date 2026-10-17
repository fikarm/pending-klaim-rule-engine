from decimal import Decimal

import pytest

from pending_klaim_rule_engine.cli import collect_review_form
from pending_klaim_rule_engine.review_service import (
    CriterionReview,
    ReviewReport,
    format_review_report,
)


def test_cli_collects_e87_6_structured_evidence():
    answers = iter(
        [
            "E87.6",
            "2.95",
            "mmol/L",
            "Lab page 2",
            "ya",
            "Medication page 4",
        ]
    )

    form = collect_review_form(lambda prompt: next(answers), position_required=False)

    assert form.diagnosis_code == "E87.6"
    assert form.diagnosis_position is None
    assert form.potassium_value == Decimal("2.95")
    assert form.kcl_injection is True
    assert form.kcl_reference == "Medication page 4"


def test_cli_collects_position_only_when_rule_requires_it():
    answers = iter(["secondary", "2.95", "mmol/L", "Lab page 2", "ya", "Med page 4"])

    form = collect_review_form(
        lambda prompt: next(answers),
        diagnosis_code="E87.6",
        position_required=True,
    )

    assert form.diagnosis_position == "secondary"


def test_cli_rejects_unrecognized_treatment_answer():
    answers = iter(["E87.6", "", "maybe", "Medication page 4"])

    with pytest.raises(ValueError, match="kcl_injection must be true or false"):
        collect_review_form(lambda prompt: next(answers))


def test_review_report_shows_outcomes_and_provenance_without_claim_decision():
    report = ReviewReport(
        evaluation_id=7,
        diagnosis_code="E87.6",
        diagnosis_position=None,
        outcome="evidence_not_found",
        rule_version_id=3,
        rule_version_number=2,
        criteria=(
            CriterionReview(
                criterion_id="potassium_below_3_00",
                description="Nilai kalium < 3,00",
                outcome="evidence_not_found",
                evidence_value=None,
                evidence_reference=None,
            ),
        ),
        operational_reference="page 12",
        official_reference="section 11",
    )

    output = format_review_report(report)

    assert "BUKTI BELUM DITEMUKAN" in output
    assert "Rujukan rule RSDS: page 12" in output
    assert "Rujukan sumber resmi: section 11" in output
    assert "bukan keputusan penerimaan klaim" in output
    assert "Posisi diagnosis:" not in output