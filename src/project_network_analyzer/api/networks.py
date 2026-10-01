"""
networks.py — Saved networks and their interpretations.

    POST /networks                        save a network with its analysis
    GET  /networks                        list saved networks, newest first
    GET  /networks/{id}                   one saved network, with its analysis
    POST /networks/{id}/interpretations   ask the agent about it
    GET  /networks/{id}/interpretations   what the agent has said, newest first

A saved network is immutable, and its analysis is computed once, when it
is saved. Since the analysis is deterministic, what is stored is exactly
what `/analysis` would return for the same payload.

An interpretation is one agent call over that STORED report: the network
is never re-analysed, and the agent sees only the report text. Only model
replies are saved (201). A fallback notice is returned but not saved
(200, `id` null): it says nothing about the network, and storing it would
fill the history with copies of the same notice.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from project_network_analyzer.agent.llm_agent import LLMAgent
from project_network_analyzer.api.schemas import (
    ActivityOut,
    AnalysisOut,
    InterpretationIn,
    InterpretationOut,
    InterpretationPage,
    NetworkIn,
    NetworkOut,
    NetworkPage,
    NetworkSummary,
    ProjectOut,
    ValidationOut,
)
from project_network_analyzer.api.shared import build_network, get_agent, get_session
from project_network_analyzer.infrastructure.db.models import NetworkRow
from project_network_analyzer.infrastructure.db.repository import (
    InterpretationRepository,
    NetworkRepository,
)
from project_network_analyzer.services.pipeline import analyze_network

router = APIRouter(prefix="/networks", tags=["networks"])


def _not_found(network_id: uuid.UUID) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Network {network_id} not found.")


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
        raise _not_found(network_id)
    return _network_out(row)


@router.post(
    "/{network_id}/interpretations",
    response_model=InterpretationOut,
    status_code=201,
    responses={200: {"description": "The agent fell back; nothing was saved."}},
)
def create_interpretation(
    network_id: uuid.UUID,
    payload: InterpretationIn,
    response: Response,
    session: Session = Depends(get_session),
    agent: LLMAgent = Depends(get_agent),
) -> InterpretationOut:
    """
    Interpret the saved network's stored report, or answer a question
    about it: one agent call either way.
    """
    report = NetworkRepository(session).get_report(network_id)
    if report is None:
        raise _not_found(network_id)
    # End the read transaction: it must not stay open through the model call.
    session.rollback()

    question = payload.question or None
    reply = agent.answer(question, report) if question else agent.interpret(report)
    if not reply.from_llm:
        response.status_code = 200
        return InterpretationOut(
            id=None, created_at=None, question=question, model=None, text=reply.text
        )

    row = InterpretationRepository(session).add(network_id, question, agent.model, reply.text)
    session.commit()
    return InterpretationOut.model_validate(row)


@router.get("/{network_id}/interpretations", response_model=InterpretationPage)
def list_interpretations(
    network_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> InterpretationPage:
    if not NetworkRepository(session).exists(network_id):
        raise _not_found(network_id)
    items, total = InterpretationRepository(session).list_for(network_id, limit, offset)
    return InterpretationPage(
        items=[InterpretationOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
