from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pending_klaim_rule_engine.models import (
    ClaimEvaluation,
    CodingRule,
    RuleVersion,
    SourceDocument,
)
from pending_klaim_rule_engine.rule_lifecycle import (
    InvalidRuleTransition,
    activate_rule_version,
    create_rule_revision,
    get_active_rule_version,
    review_rule_version,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def session(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'lifecycle-test.db'}"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with Session(engine) as session:
        yield session
        session.rollback()
    engine.dispose()


def _add_rule_version(session, version_number, status="draft"):
    source = SourceDocument(
        source_type="rsds_interpretation",
        title="Synthetic source",
        verification_status="verified",
    )
    session.add(source)
    session.flush()
    rule = session.scalar(select_rule())
    if rule is None:
        rule = CodingRule(code="E87.6", name="Hipokalemia")
        session.add(rule)
        session.flush()
    version = RuleVersion(
        rule_id=rule.id,
        version=version_number,
        status=status,
        operator="all",
        criteria=[{"id": "synthetic", "type": "treatment_present"}],
        operational_source_id=source.id,
        operational_reference="page 1",
    )
    session.add(version)
    session.flush()
    return version


def select_rule():
    from sqlalchemy import select

    return select(CodingRule).where(CodingRule.code == "E87.6")


def test_draft_rule_cannot_be_activated(session):
    version = _add_rule_version(session, 1)

    with pytest.raises(InvalidRuleTransition, match="Only reviewed"):
        activate_rule_version(session, version.id)

    assert version.status == "draft"
    assert get_active_rule_version(session, "E87.6") is None


def test_reviewed_rule_can_be_activated_and_returned_as_active(session):
    version = _add_rule_version(session, 1)

    reviewed = review_rule_version(session, version.id)
    active = activate_rule_version(session, reviewed.id)

    assert active.status == "active"
    assert get_active_rule_version(session, "E87.6").id == active.id


def test_activating_new_version_retires_previous_active_version(session):
    first = _add_rule_version(session, 1, status="active")
    second = _add_rule_version(session, 2)

    review_rule_version(session, second.id)
    activate_rule_version(session, second.id)

    assert first.status == "retired"
    assert get_active_rule_version(session, "E87.6").id == second.id


def test_revision_preserves_existing_evaluation_rule_version(session):
    first = _add_rule_version(session, 1, status="active")
    evaluation = ClaimEvaluation(
        rule_version_id=first.id,
        diagnosis_code="E87.6",
        outcome="met",
    )
    session.add(evaluation)
    session.flush()

    second = create_rule_revision(
        session,
        first.id,
        criteria=[{"id": "synthetic", "type": "treatment_present", "expected": False}],
    )
    review_rule_version(session, second.id)
    activate_rule_version(session, second.id)

    stored_evaluation = session.get(ClaimEvaluation, evaluation.id)
    stored_first = session.get(RuleVersion, first.id)
    active = get_active_rule_version(session, "E87.6")

    assert second.version == 2
    assert second.status == "active"
    assert stored_evaluation.rule_version_id == first.id
    assert stored_first.status == "retired"
    assert stored_first.criteria == [
        {"id": "synthetic", "type": "treatment_present"}
    ]
    assert active.id == second.id


def test_rule_version_criteria_cannot_be_changed_after_creation(session):
    version = _add_rule_version(session, 1, status="active")
    version.criteria = [{"id": "changed", "type": "treatment_present"}]

    with pytest.raises(ValueError, match="immutable after creation"):
        session.flush()