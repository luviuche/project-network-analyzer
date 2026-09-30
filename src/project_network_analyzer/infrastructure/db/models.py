"""
models.py — The relational schema, as SQLAlchemy models.

    networks      one row per saved network (immutable once saved)
    activities    its nodes, keyed by (network_id, key)
    precedences   its edges; both ends reference activities of the SAME
                  network, through composite foreign keys
    analyses      the deterministic result, one per network

The database enforces what it can express on its own: an activity key is
unique within its network, a precedence joins two activities that exist
in that network, and no activity precedes itself. Acyclicity and
connectivity it cannot express; those stay with the domain, which also
runs first, so these constraints are a second line of defence rather
than the validation itself.

`position` columns keep the order the activities and each predecessor
list were declared in. Rebuilding a network in that order gives back the
same graph, down to adjacency order, which is what decides the cycle
`Network.detect_cycle` reports.

The analysis is derived data, stored as JSONB: it is never queried by
field, only returned whole. `is_valid` gets its own column because the
listing does filter and display by it.

Changing anything here needs an Alembic migration; the test suite checks
that the two agree.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    MetaData,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Deterministic constraint names, so migrations can refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class NetworkRow(Base):
    __tablename__ = "networks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    # Set in Python rather than with now(): inside one transaction now() is
    # constant, and the listing orders by this column.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    activities: Mapped[list[ActivityRow]] = relationship(
        back_populates="network",
        cascade="all, delete-orphan",
        order_by="ActivityRow.position",
        lazy="selectin",
    )
    analysis: Mapped[AnalysisRow] = relationship(
        back_populates="network",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class ActivityRow(Base):
    __tablename__ = "activities"

    network_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("networks.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int]
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)

    network: Mapped[NetworkRow] = relationship(back_populates="activities")
    # This activity's predecessors, in declaration order.
    predecessor_links: Mapped[list[PrecedenceRow]] = relationship(
        foreign_keys="[PrecedenceRow.network_id, PrecedenceRow.activity_key]",
        cascade="all, delete-orphan",
        order_by="PrecedenceRow.position",
        lazy="selectin",
    )


class PrecedenceRow(Base):
    """`predecessor_key` must finish before `activity_key` starts."""

    __tablename__ = "precedences"

    network_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    activity_key: Mapped[str] = mapped_column(Text, primary_key=True)
    predecessor_key: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int]

    __table_args__ = (
        ForeignKeyConstraint(
            ["network_id", "activity_key"],
            ["activities.network_id", "activities.key"],
            ondelete="CASCADE",
            name="fk_precedences_activity_activities",
        ),
        ForeignKeyConstraint(
            ["network_id", "predecessor_key"],
            ["activities.network_id", "activities.key"],
            ondelete="CASCADE",
            name="fk_precedences_predecessor_activities",
        ),
        CheckConstraint("activity_key <> predecessor_key", name="no_self_precedence"),
    )


class AnalysisRow(Base):
    __tablename__ = "analyses"

    network_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("networks.id", ondelete="CASCADE"), primary_key=True
    )
    is_valid: Mapped[bool]
    validation: Mapped[dict] = mapped_column(JSONB)
    # SQL NULL, not JSON null, when the network failed validation.
    analysis: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    findings: Mapped[list[str]] = mapped_column(JSONB)
    report: Mapped[str] = mapped_column(Text)

    network: Mapped[NetworkRow] = relationship(back_populates="analysis")
