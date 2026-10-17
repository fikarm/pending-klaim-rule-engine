from sqlalchemy.orm import Session

from pending_klaim_rule_engine.database import create_database_engine
from pending_klaim_rule_engine.models import CodingRule, RuleVersion, SourceDocument
from pending_klaim_rule_engine.review_service import serialize_rule
from pending_klaim_rule_engine.rule_engine import E87_6_RULE
from pending_klaim_rule_engine.rule_lifecycle import (
    activate_rule_version,
    get_active_rule_version,
    review_rule_version,
)


def seed_demo_data(session: Session) -> RuleVersion:
    active_version = get_active_rule_version(session, E87_6_RULE.code)
    if active_version is not None:
        return active_version

    source = SourceDocument(
        source_type="other",
        title="Synthetic development fixture based on RSDS rule_rsds.pdf",
        version_label="development-only",
        verification_status="verified",
    )
    session.add(source)
    session.flush()

    rule = session.scalar(
        select_rule_by_code(E87_6_RULE.code)
    )
    if rule is None:
        rule = CodingRule(code=E87_6_RULE.code, name=E87_6_RULE.name)
        session.add(rule)
        session.flush()

    latest_version = session.scalar(
        select_latest_rule_version(rule.id)
    )
    version = RuleVersion(
        rule_id=rule.id,
        version=(latest_version.version + 1) if latest_version else 1,
        status="draft",
        operator=E87_6_RULE.operator,
        criteria=serialize_rule(E87_6_RULE),
        operational_source_id=source.id,
        operational_reference="Synthetic example based on RSDS rule_rsds.pdf page 12",
    )
    session.add(version)
    session.flush()
    review_rule_version(session, version.id)
    return activate_rule_version(session, version.id)


def select_rule_by_code(code: str):
    from sqlalchemy import select

    return select(CodingRule).where(CodingRule.code == code)


def select_latest_rule_version(rule_id: int):
    from sqlalchemy import select

    return (
        select(RuleVersion)
        .where(RuleVersion.rule_id == rule_id)
        .order_by(RuleVersion.version.desc())
        .limit(1)
    )


def main() -> None:
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            version = seed_demo_data(session)
            version_number = version.version
            session.commit()
        print(
            f"Synthetic E87.6 development rule is active at version {version_number}. "
            "Do not use this fixture for real claims."
        )
    finally:
        engine.dispose()