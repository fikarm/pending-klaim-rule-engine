"""Create source, rule, and evaluation tables.

Revision ID: 0001_initial_schema
Revises:
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("version_label", sa.String(length=100)),
        sa.Column(
            "verification_status",
            sa.String(length=20),
            server_default="unverified",
            nullable=False,
        ),
        sa.Column("sha256", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('rsds_interpretation', 'official', 'other')",
            name="ck_source_documents_source_type",
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified', 'verified')",
            name="ck_source_documents_verification_status",
        ),
    )
    op.create_table(
        "coding_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=16), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
    )
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("operator", sa.String(length=8), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("operational_source_id", sa.Integer(), nullable=False),
        sa.Column("operational_reference", sa.String(length=200)),
        sa.Column("official_source_id", sa.Integer()),
        sa.Column("official_reference", sa.String(length=200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_rule_versions_positive_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'reviewed', 'active', 'retired')",
            name="ck_rule_versions_status",
        ),
        sa.CheckConstraint("operator IN ('all', 'any')", name="ck_rule_versions_operator"),
        sa.ForeignKeyConstraint(["rule_id"], ["coding_rules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["operational_source_id"], ["source_documents.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["official_source_id"], ["source_documents.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("rule_id", "version", name="uq_rule_versions_rule_version"),
    )
    op.create_table(
        "claim_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_version_id", sa.Integer(), nullable=False),
        sa.Column("diagnosis_code", sa.String(length=16), nullable=False),
        sa.Column("diagnosis_position", sa.String(length=16)),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('met', 'not_met', 'evidence_not_found')",
            name="ck_claim_evaluations_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"], ["rule_versions.id"], ondelete="RESTRICT"
        ),
    )
    op.create_table(
        "evaluation_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("criterion_id", sa.String(length=100), nullable=False),
        sa.Column("evidence_key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source_reference", sa.Text()),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["claim_evaluations.id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "criterion_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("criterion_id", sa.String(length=100), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("evidence_id", sa.Integer()),
        sa.CheckConstraint(
            "outcome IN ('met', 'not_met', 'evidence_not_found')",
            name="ck_criterion_outcomes_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["claim_evaluations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evaluation_evidence.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "evaluation_id", "criterion_id", name="uq_criterion_outcomes_evaluation"
        ),
    )


def downgrade() -> None:
    op.drop_table("criterion_outcomes")
    op.drop_table("evaluation_evidence")
    op.drop_table("claim_evaluations")
    op.drop_table("rule_versions")
    op.drop_table("coding_rules")
    op.drop_table("source_documents")