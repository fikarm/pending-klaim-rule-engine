from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
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


ROOT = Path(__file__).resolve().parents[1]


def _round_trip_records(engine: Engine) -> None:
    with Session(engine) as session, session.begin():
        rsds_source = SourceDocument(
            source_type="rsds_interpretation",
            title="Synthetic RSDS rules",
            version_label="2019",
            verification_status="verified",
            sha256="a" * 64,
        )
        official_source = SourceDocument(
            source_type="official",
            title="Synthetic official source",
            verification_status="unverified",
        )
        session.add_all([rsds_source, official_source])
        session.flush()

        rule = CodingRule(code="E87.6", name="Hipokalemia")
        session.add(rule)
        session.flush()

        rule_version = RuleVersion(
            rule_id=rule.id,
            version=1,
            status="active",
            operator="all",
            criteria=[
                {"id": "potassium_below_3_00", "threshold": "3.00"},
                {"id": "kcl_injection", "type": "treatment_present"},
            ],
            operational_source_id=rsds_source.id,
            operational_reference="page 12",
            official_source_id=official_source.id,
            official_reference="section 11",
        )
        session.add(rule_version)
        session.flush()

        evaluation = ClaimEvaluation(
            rule_version_id=rule_version.id,
            diagnosis_code="E87.6",
            outcome="met",
        )
        session.add(evaluation)
        session.flush()

        evidence = EvaluationEvidence(
            evaluation_id=evaluation.id,
            criterion_id="potassium_below_3_00",
            evidence_key="potassium",
            value=2.99,
            source_reference="synthetic lab result page 1",
        )
        session.add(evidence)
        session.flush()

        outcome = CriterionOutcomeRecord(
            evaluation_id=evaluation.id,
            criterion_id="potassium_below_3_00",
            outcome="met",
            evidence_id=evidence.id,
        )
        session.add(outcome)
        session.flush()
        evaluation_id = evaluation.id
        rule_version_id = rule_version.id

    with Session(engine) as session:
        stored_evaluation = session.get(ClaimEvaluation, evaluation_id)
        stored_version = session.get(RuleVersion, rule_version_id)
        stored_outcome = session.scalar(
            select(CriterionOutcomeRecord).where(
                CriterionOutcomeRecord.evaluation_id == evaluation_id
            )
        )

    assert stored_evaluation is not None
    assert stored_evaluation.diagnosis_code == "E87.6"
    assert stored_evaluation.outcome == "met"
    assert stored_version is not None
    assert stored_version.criteria[0]["threshold"] == "3.00"
    assert stored_version.operational_reference == "page 12"
    assert stored_version.official_reference == "section 11"
    assert stored_outcome is not None
    assert stored_outcome.evidence_id is not None


def test_migration_and_records_round_trip_on_sqlite(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'review-test.db'}"
    engine = migrate_database(database_url)

    try:
        _round_trip_records(engine)
    finally:
        engine.dispose()


def test_migration_and_records_round_trip_on_postgresql(postgres_engine):
    _round_trip_records(postgres_engine)