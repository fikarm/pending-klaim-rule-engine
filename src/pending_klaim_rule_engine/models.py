from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    inspect,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, Mapped, Mapper, mapped_column


class Base(DeclarativeBase):
    pass


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('rsds_interpretation', 'official', 'other')",
            name="ck_source_documents_source_type",
        ),
        CheckConstraint(
            "verification_status IN ('unverified', 'verified')",
            name="ck_source_documents_verification_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(100))
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unverified", server_default="unverified"
    )
    sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CodingRule(Base):
    __tablename__ = "coding_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class RuleVersion(Base):
    __tablename__ = "rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_id", "version", name="uq_rule_versions_rule_version"),
        CheckConstraint("version > 0", name="ck_rule_versions_positive_version"),
        CheckConstraint(
            "status IN ('draft', 'reviewed', 'active', 'retired')",
            name="ck_rule_versions_status",
        ),
        CheckConstraint(
            "operator IN ('all', 'any')", name="ck_rule_versions_operator"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("coding_rules.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    operator: Mapped[str] = mapped_column(String(8), nullable=False)
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    operational_source_id: Mapped[int] = mapped_column(
        ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False
    )
    operational_reference: Mapped[str | None] = mapped_column(String(200))
    official_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_documents.id", ondelete="RESTRICT")
    )
    official_reference: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# Freeze rule contents for reproducible evaluations; lifecycle status may change.
@event.listens_for(RuleVersion, "before_update")
def prevent_rule_version_snapshot_changes(
    mapper: Mapper[RuleVersion], connection: Connection, version: RuleVersion
) -> None:
    """Reject changes to a rule snapshot while permitting lifecycle transitions."""
    immutable_fields = (
        "rule_id",
        "version",
        "operator",
        "criteria",
        "operational_source_id",
        "operational_reference",
        "official_source_id",
        "official_reference",
    )
    state = inspect(version)
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("Rule version contents are immutable after creation")


class ClaimEvaluation(Base):
    __tablename__ = "claim_evaluations"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('met', 'not_met', 'evidence_not_found')",
            name="ck_claim_evaluations_outcome",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_version_id: Mapped[int] = mapped_column(
        ForeignKey("rule_versions.id", ondelete="RESTRICT"), nullable=False
    )
    diagnosis_code: Mapped[str] = mapped_column(String(16), nullable=False)
    diagnosis_position: Mapped[str | None] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvaluationEvidence(Base):
    __tablename__ = "evaluation_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("claim_evaluations.id", ondelete="CASCADE"), nullable=False
    )
    criterion_id: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text)


class CriterionOutcomeRecord(Base):
    __tablename__ = "criterion_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_id", "criterion_id", name="uq_criterion_outcomes_evaluation"
        ),
        CheckConstraint(
            "outcome IN ('met', 'not_met', 'evidence_not_found')",
            name="ck_criterion_outcomes_outcome",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("claim_evaluations.id", ondelete="CASCADE"), nullable=False
    )
    criterion_id: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_evidence.id", ondelete="SET NULL")
    )