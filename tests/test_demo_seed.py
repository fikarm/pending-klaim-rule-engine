from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from conftest import migrate_database
from pending_klaim_rule_engine.demo_seed import seed_demo_data
from pending_klaim_rule_engine.models import SourceDocument
from pending_klaim_rule_engine.rule_lifecycle import get_active_rule_version


@pytest.fixture
def session(tmp_path):
    engine = migrate_database(f"sqlite:///{tmp_path / 'demo-seed-test.db'}")
    with Session(engine) as session:
        yield session
        session.rollback()
    engine.dispose()


def test_demo_seed_creates_reusable_synthetic_active_rule(session):
    first = seed_demo_data(session)
    session.commit()
    second = seed_demo_data(session)

    source = session.get(SourceDocument, first.operational_source_id)

    assert first.id == second.id
    assert first.status == "active"
    assert source.source_type == "other"
    assert source.title.startswith("Synthetic development fixture")
    assert source.version_label == "development-only"
    assert get_active_rule_version(session, "E87.6").id == first.id