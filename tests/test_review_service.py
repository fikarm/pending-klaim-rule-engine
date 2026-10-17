from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from conftest import migrate_database
from pending_klaim_rule_engine.models import (
    ClaimEvaluation,
    CodingRule,
    CriterionOutcomeRecord,
    EvaluationEvidence,
    RuleVersion,
    SourceDocument,
)
from pending_klaim_rule_engine.review_form import StructuredClaimForm
from pending_klaim_rule_engine.review_service import (
    NoActiveRuleError,
    evaluate_claim,
    serialize_rule,
)
from pending_klaim_rule_engine.rule_engine import E87_6_RULE


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def session(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'review-service-test.db'}"
    engine = migrate_database(database_url)
    with Session(engine) as session:
        _seed_active_e87_6_rule(session)
        yield session
        session.rollback()
    engine.dispose()


def _seed_active_e87_6_rule(session):
    source = SourceDocument(
        source_type="rsds_interpretation",
        title="Synthetic RSDS source",
        verification_status="verified",
    )
    session.add(source)
    session.flush()
    rule = CodingRule(code="E87.6", name="Hipokalemia")
    session.add(rule)
    session.flush()
    session.add(
        RuleVersion(
            rule_id=rule.id,
            version=1,
            status="active",
            operator=E87_6_RULE.operator,
            criteria=serialize_rule(E87_6_RULE),
            operational_source_id=source.id,
            operational_reference="page 12",
            official_reference="section 11",
        )
    )
    session.flush()


def test_review_persists_rule_version_evidence_and_criterion_outcomes(session):
    form = StructuredClaimForm.from_fields(
        {
            "diagnosis_code": "E87.6",
            "potassium_value": "2.95",
            "potassium_unit": "mmol/L",
            "potassium_reference": "Lab page 2",
            "kcl_injection": "true",
            "kcl_reference": "Medication page 4",
        }
    )

    report = evaluate_claim(session, form)
    session.commit()

    evaluation = session.get(ClaimEvaluation, report.evaluation_id)
    outcomes = session.scalars(
        select(CriterionOutcomeRecord).where(
            CriterionOutcomeRecord.evaluation_id == report.evaluation_id
        )
    ).all()
    evidence = session.scalars(
        select(EvaluationEvidence).where(
            EvaluationEvidence.evaluation_id == report.evaluation_id
        )
    ).all()

    assert report.outcome == "met"
    assert report.rule_version_number == 1
    assert report.operational_reference == "page 12"
    assert evaluation.rule_version_id == report.rule_version_id
    assert {outcome.outcome for outcome in outcomes} == {"met"}
    assert {item.source_reference for item in evidence} == {
        "Lab page 2",
        "Medication page 4",
    }


def test_missing_evidence_is_persisted_without_inventing_evidence(session):
    form = StructuredClaimForm.from_fields({"diagnosis_code": "E87.6"})

    report = evaluate_claim(session, form)
    outcomes = session.scalars(
        select(CriterionOutcomeRecord).where(
            CriterionOutcomeRecord.evaluation_id == report.evaluation_id
        )
    ).all()
    evidence = session.scalars(
        select(EvaluationEvidence).where(
            EvaluationEvidence.evaluation_id == report.evaluation_id
        )
    ).all()

    assert report.outcome == "evidence_not_found"
    assert {outcome.outcome for outcome in outcomes} == {"evidence_not_found"}
    assert all(outcome.evidence_id is None for outcome in outcomes)
    assert evidence == []


def test_review_requires_an_active_rule(session):
    form = StructuredClaimForm.from_fields({"diagnosis_code": "R18"})

    with pytest.raises(NoActiveRuleError, match="No active rule"):
        evaluate_claim(session, form)


def test_review_persists_end_to_end_on_postgresql(postgres_engine):
    with Session(postgres_engine) as session:
        _seed_active_e87_6_rule(session)
        form = StructuredClaimForm.from_fields(
            {
                "diagnosis_code": "E87.6",
                "potassium_value": "2.95",
                "potassium_unit": "mmol/L",
                "potassium_reference": "Synthetic lab page 1",
                "kcl_injection": "true",
                "kcl_reference": "Synthetic medication page 2",
            }
        )

        report = evaluate_claim(session, form)
        session.commit()

        stored = session.get(ClaimEvaluation, report.evaluation_id)
        outcomes = session.scalars(
            select(CriterionOutcomeRecord).where(
                CriterionOutcomeRecord.evaluation_id == report.evaluation_id
            )
        ).all()

    assert stored.outcome == "met"
    assert stored.rule_version_id == report.rule_version_id
    assert {item.outcome for item in outcomes} == {"met"}