"""
shared.py — Dependencies and helpers used by more than one router.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from project_network_analyzer.agent.llm_agent import LLMAgent
from project_network_analyzer.api.schemas import NetworkIn, ProjectOut
from project_network_analyzer.domain.network import Network


def get_agent(request: Request) -> LLMAgent:
    """The agent built once at startup (see `create_app`)."""
    return request.app.state.agent


def get_session(request: Request) -> Iterator[Session]:
    """
    One session per request, closed afterwards. Without a configured
    database the persistence endpoints answer 503, while the stateless
    ones keep working.
    """
    factory = request.app.state.session_factory
    if factory is None:
        raise HTTPException(
            status_code=503,
            detail="Persistence is not configured: set PNA_DATABASE_URL.",
        )
    with factory() as session:
        yield session


def build_network(payload: NetworkIn) -> Network:
    """Raises NetworkStructureError, which the app turns into a 422."""
    return Network.from_dict(payload.to_domain_dict())


def project_out(network: Network) -> ProjectOut:
    return ProjectOut(name=network.project_name, description=network.description)
