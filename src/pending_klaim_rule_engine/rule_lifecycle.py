"""Lifecycle helpers for creating, reviewing, and activating rule versions."""

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import Session

from pending_klaim_rule_engine.models import CodingRule, RuleVersion


class InvalidRuleTransition(ValueError):
    """Raised when a rule version is moved through an unsupported lifecycle state."""


def create_rule_revision(
    session: Session,
    source_version_id: int,
    *,
    criteria: list[dict[str, object]],
    operator: str | None = None,
    operational_source_id: int | None = None,
    operational_reference: str | None = None,
    official_source_id: int | None = None,
    official_reference: str | None = None,
) -> RuleVersion:
    """Create a new draft revision based on a previously approved rule version."""
    source_version = session.scalar(
        select(RuleVersion)
        .where(RuleVersion.id == source_version_id)
        .with_for_update()
    )
    if source_version is None:
        raise LookupError(f"Rule version {source_version_id} does not exist")
    if source_version.status == "draft":
        raise InvalidRuleTransition("A draft rule version cannot be revised")

    rule = session.scalar(
        select(CodingRule)
        .where(CodingRule.id == source_version.rule_id)
        .with_for_update()
    )
    if rule is None:
        raise LookupError(f"Coding rule {source_version.rule_id} does not exist")

    latest_version = session.scalar(
        select(RuleVersion)
        .where(RuleVersion.rule_id == rule.id)
        .order_by(RuleVersion.version.desc())
        .limit(1)
        .with_for_update()
    )
    next_version_number = latest_version.version + 1
    version = RuleVersion(
        rule_id=rule.id,
        version=next_version_number,
        status="draft",
        operator=operator or source_version.operator,
        criteria=deepcopy(criteria),
        operational_source_id=operational_source_id or source_version.operational_source_id,
        operational_reference=(
            operational_reference
            if operational_reference is not None
            else source_version.operational_reference
        ),
        official_source_id=(
            official_source_id
            if official_source_id is not None
            else source_version.official_source_id
        ),
        official_reference=(
            official_reference
            if official_reference is not None
            else source_version.official_reference
        ),
    )
    session.add(version)
    session.flush()
    return version


def review_rule_version(session: Session, version_id: int) -> RuleVersion:
    """Move a draft rule version into the reviewed state for activation."""
    version = session.scalar(
        select(RuleVersion)
        .where(RuleVersion.id == version_id)
        .with_for_update()
    )
    if version is None:
        raise LookupError(f"Rule version {version_id} does not exist")
    if version.status != "draft":
        raise InvalidRuleTransition("Only draft rule versions can be reviewed")

    version.status = "reviewed"
    session.flush()
    return version


def activate_rule_version(session: Session, version_id: int) -> RuleVersion:
    """Activate the candidate rule version and retire any active version for it."""
    candidate = session.scalar(
        select(RuleVersion)
        .where(RuleVersion.id == version_id)
        .with_for_update()
    )
    if candidate is None:
        raise LookupError(f"Rule version {version_id} does not exist")

    rule = session.scalar(
        select(CodingRule)
        .where(CodingRule.id == candidate.rule_id)
        .with_for_update()
    )
    if rule is None:
        raise LookupError(f"Coding rule {candidate.rule_id} does not exist")
    if candidate.status != "reviewed":
        raise InvalidRuleTransition("Only reviewed rule versions can be activated")

    active_versions = session.scalars(
        select(RuleVersion)
        .where(
            RuleVersion.rule_id == rule.id,
            RuleVersion.status == "active",
        )
        .with_for_update()
    ).all()
    for active_version in active_versions:
        active_version.status = "retired"

    candidate.status = "active"
    session.flush()
    return candidate


def get_active_rule_version(session: Session, code: str) -> RuleVersion | None:
    """Return the active rule version for the supplied diagnosis code, if any."""
    return session.scalar(
        select(RuleVersion)
        .join(CodingRule, RuleVersion.rule_id == CodingRule.id)
        .where(CodingRule.code == code, RuleVersion.status == "active")
    )