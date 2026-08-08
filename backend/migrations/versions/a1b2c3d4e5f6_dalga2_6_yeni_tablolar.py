"""dalga2-6 yeni tablolar: review_assignments, challenges, self_assessments

create_all bu tablolari calisan sistemde zaten olusturdu; bu migration Alembic
yoluyla kurulan TEMIZ bir veritabani icin ayni semayi uretir. Mevcut sistemde
tablolar varsa `alembic stamp head` ile isaretlenir (yeniden olusturulmaz).

Revision ID: a1b2c3d4e5f6
Revises: 97f6233bb04b
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "97f6233bb04b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), index=True),
        sa.Column("call_id", sa.Integer(), sa.ForeignKey("calls.id", ondelete="CASCADE"), index=True),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("assigner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.String(length=16), server_default="manual"),
        sa.Column("status", sa.String(length=16), server_default="assigned", index=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("manual_evaluations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("call_id", "reviewer_id", name="uq_review_call_reviewer"),
    )
    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), index=True),
        sa.Column("title", sa.String(length=128)),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("metric", sa.String(length=24), server_default="score_above"),
        sa.Column("threshold", sa.Float(), server_default="85.0"),
        sa.Column("target", sa.Integer(), server_default="10"),
        sa.Column("reward_points", sa.Integer(), server_default="100"),
        sa.Column("starts_at", sa.DateTime()),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), index=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "self_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), index=True),
        sa.Column("call_id", sa.Integer(), sa.ForeignKey("calls.id", ondelete="CASCADE"), index=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id", ondelete="CASCADE"), index=True),
        sa.Column("self_score", sa.Float()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("call_id", "agent_id", name="uq_self_call_agent"),
    )


def downgrade() -> None:
    op.drop_table("self_assessments")
    op.drop_table("challenges")
    op.drop_table("review_assignments")
