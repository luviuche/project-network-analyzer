"""create interpretations

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-30 21:44:19.109041

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interpretations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("network_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["network_id"],
            ["networks.id"],
            name=op.f("fk_interpretations_network_id_networks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interpretations")),
    )
    op.create_index(
        "ix_interpretations_network_id_created_at",
        "interpretations",
        ["network_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_interpretations_network_id_created_at", table_name="interpretations")
    op.drop_table("interpretations")
