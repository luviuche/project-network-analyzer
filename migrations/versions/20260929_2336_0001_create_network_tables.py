"""create networks, activities, precedences and analyses

Revision ID: 0001
Revises:
Create Date: 2026-09-29 23:36:30.340423

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "networks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networks")),
    )
    op.create_index(
        op.f("ix_networks_created_at"), "networks", ["created_at"], unique=False
    )

    op.create_table(
        "activities",
        sa.Column("network_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["network_id"],
            ["networks.id"],
            name=op.f("fk_activities_network_id_networks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("network_id", "key", name=op.f("pk_activities")),
    )

    op.create_table(
        "analyses",
        sa.Column("network_id", sa.Uuid(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "analysis",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["network_id"],
            ["networks.id"],
            name=op.f("fk_analyses_network_id_networks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("network_id", name=op.f("pk_analyses")),
    )

    op.create_table(
        "precedences",
        sa.Column("network_id", sa.Uuid(), nullable=False),
        sa.Column("activity_key", sa.Text(), nullable=False),
        sa.Column("predecessor_key", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "activity_key <> predecessor_key",
            name=op.f("ck_precedences_no_self_precedence"),
        ),
        # Both ends reference an activity of the same network.
        sa.ForeignKeyConstraint(
            ["network_id", "activity_key"],
            ["activities.network_id", "activities.key"],
            name="fk_precedences_activity_activities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["network_id", "predecessor_key"],
            ["activities.network_id", "activities.key"],
            name="fk_precedences_predecessor_activities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "network_id", "activity_key", "predecessor_key", name=op.f("pk_precedences")
        ),
    )


def downgrade() -> None:
    op.drop_table("precedences")
    op.drop_table("analyses")
    op.drop_table("activities")
    op.drop_index(op.f("ix_networks_created_at"), table_name="networks")
    op.drop_table("networks")
