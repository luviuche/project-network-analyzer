"""
networks.py — Saved networks.

    POST /networks        save a network with its analysis
    GET  /networks        list saved networks, newest first
    GET  /networks/{id}   one saved network, with its stored analysis

A saved network is immutable, and its analysis is computed once, when it
is saved. Since the analysis is deterministic, what is stored is exactly
what `/analysis` would return for the same payload.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from project_network_analyzer.api.schemas import (
    ActivityOut,
    AnalysisOut,
    NetworkIn,
    NetworkOut,
    NetworkPage,
    NetworkSummary,
    ProjectOut,
    ValidationOut,
)
from project_network_analyzer.api.shared import build_network, get_session
from project_network_analyzer.infrastructure.db.models import NetworkRow
from project_network_analyzer.infrastructure.db.repository import NetworkRepository
from project_network_analyzer.services.pipeline import analyze_network

router = APIRouter(prefix="/networks", tags=["networks"])


def _network_out(row: NetworkRow) -> NetworkOut:
    stored = row.analysis
    return NetworkOut(
        id=row.id,
        created_at=row.created_at,
        project=ProjectOut(name=row.name, description=row.description),
        activities=[
            ActivityOut(
                id=activity.key,
                name=activity.name,
                description=activity.description,
                predecessors=[link.predecessor_key for link in activity.predecessor_links],
            )
            for activity in row.activities
        ],
        validation=ValidationOut.model_validate(stored.validation),
        analysis=(
            AnalysisOut.model_validate(stored.analysis)
            if stored.analysis is not None
            else None
        ),
        findings=stored.findings,
        report=stored.report,
    )


@router.post("", response_model=NetworkOut, status_code=201)
def create_network(
    payload: NetworkIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> NetworkOut:
    """
    Save a network and its analysis. As with `/analysis`, a network that
    fails validation is still saved: its validation result is the answer.
    """
    network = build_network(payload)
    row = NetworkRepository(session).add(network, analyze_network(network))
    session.commit()
    response.headers["Location"] = str(request.url_for("get_network", network_id=row.id))
    return _network_out(row)


@router.get("", response_model=NetworkPage)
def list_networks(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> NetworkPage:
    items, total = NetworkRepository(session).list_summaries(limit, offset)
    return NetworkPage(
        items=[NetworkSummary.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{network_id}", response_model=NetworkOut, name="get_network")
def get_network(
    network_id: uuid.UUID, session: Session = Depends(get_session)
) -> NetworkOut:
    row = NetworkRepository(session).get(network_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Network {network_id} not found.")
    return _network_out(row)
