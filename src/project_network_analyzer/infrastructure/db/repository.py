"""
repository.py — Saving and reading networks.

Translates between the domain and the rows in `models.py`. What goes in
is a built `Network` and the `StructuralReport` the pipeline produced
for it; what comes back out can be rebuilt into the same `Network` with
`Network.from_dict`, the seam the domain already offers.

The repository never commits: the caller owns the transaction.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from project_network_analyzer.domain.network import Network
from project_network_analyzer.infrastructure.db.models import (
    ActivityRow,
    AnalysisRow,
    NetworkRow,
    PrecedenceRow,
)
from project_network_analyzer.services.pipeline import StructuralReport


class NetworkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, network: Network, report: StructuralReport) -> NetworkRow:
        """
        Stage a network and its analysis for insertion; flushed, so the
        returned row already carries its id.

        Activities and predecessors are read from the graph in insertion
        order, which is the order they were declared in. A predecessor
        listed twice appears once in the graph, and so once here.
        """
        graph = network.graph
        row = NetworkRow(
            name=network.project_name,
            description=network.description,
            activities=[
                ActivityRow(
                    key=key,
                    position=position,
                    name=graph.nodes[key]["name"],
                    description=graph.nodes[key]["description"],
                    predecessor_links=[
                        PrecedenceRow(predecessor_key=predecessor, position=index)
                        for index, predecessor in enumerate(graph.predecessors(key))
                    ],
                )
                for position, key in enumerate(graph.nodes)
            ],
            analysis=AnalysisRow(
                is_valid=report.validation.is_valid,
                validation={
                    **asdict(report.validation),
                    "is_valid": report.validation.is_valid,
                },
                analysis=(
                    asdict(report.analysis) if report.analysis is not None else None
                ),
                findings=report.findings,
                report=report.text,
            ),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def get(self, network_id: uuid.UUID) -> NetworkRow | None:
        return self.session.get(NetworkRow, network_id)

    def list_summaries(self, limit: int, offset: int) -> tuple[list[Row], int]:
        """
        One page of summaries, newest first, and the total count. Each
        summary has `id`, `name`, `created_at`, `is_valid` and
        `activity_count`; the activities themselves are not loaded.
        """
        activity_count = (
            select(func.count())
            .where(ActivityRow.network_id == NetworkRow.id)
            .correlate(NetworkRow)
            .scalar_subquery()
        )
        page = self.session.execute(
            select(
                NetworkRow.id,
                NetworkRow.name,
                NetworkRow.created_at,
                AnalysisRow.is_valid,
                activity_count.label("activity_count"),
            )
            .join(AnalysisRow)
            .order_by(NetworkRow.created_at.desc(), NetworkRow.id)
            .limit(limit)
            .offset(offset)
        ).all()
        total = self.session.scalar(select(func.count()).select_from(NetworkRow))
        return list(page), total or 0


def to_domain(row: NetworkRow) -> Network:
    """Rebuild the saved network, in its original declaration order."""
    return Network.from_dict(
        {
            "project": {"name": row.name, "description": row.description},
            "activities": [
                {
                    "id": activity.key,
                    "name": activity.name,
                    "description": activity.description,
                    "predecessors": [
                        link.predecessor_key for link in activity.predecessor_links
                    ],
                }
                for activity in row.activities
            ],
        }
    )
