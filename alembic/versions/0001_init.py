"""init: campaigns, change_log

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keitaro_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("alias", sa.String(64), nullable=False),
        sa.Column("geo", sa.String(100), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaigns_keitaro_id", "campaigns", ["keitaro_id"], unique=True)
    op.create_table(
        "change_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("change_log")
    op.drop_index("ix_campaigns_keitaro_id", table_name="campaigns")
    op.drop_table("campaigns")
