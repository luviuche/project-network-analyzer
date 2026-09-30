"""
app.py — The HTTP API.

    GET  /health           liveness check
    POST /analysis         deterministic structural analysis
    POST /interpretation   the same analysis, explained by the LLM layer
    /networks              saved networks (see networks.py)

`/analysis` never touches the LLM: it is fast, free and fully
reproducible. `/interpretation` hands the deterministic report to the
agent, which falls back to a notice when no API key is configured, so
the endpoint works either way.

Two kinds of bad input, two outcomes:

  - A network that cannot be BUILT (duplicate id, unknown predecessor,
    self-precedence) is a bad request: 422.
  - A network that is built but breaks a model constraint (a cycle, two
    disconnected parts) is a legitimate question with a legitimate
    answer: 200, with `validation.is_valid` false and no analysis.

Run it with:

    uvicorn --factory project_network_analyzer.api.app:create_app

The endpoints are plain `def`, not `async def`: the analysis is CPU
work, and both the Anthropic client and the database driver are
synchronous, so FastAPI runs them in its thread pool instead of blocking
the event loop.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from project_network_analyzer.agent.llm_agent import LLMAgent
from project_network_analyzer.api import networks
from project_network_analyzer.api.schemas import (
    AnalysisOut,
    AnalysisResponse,
    HealthResponse,
    InterpretationRequest,
    InterpretationResponse,
    NetworkIn,
    ValidationOut,
)
from project_network_analyzer.api.shared import build_network, get_agent, project_out
from project_network_analyzer.config import Settings, load_settings
from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.infrastructure.db.session import (
    build_engine,
    build_session_factory,
)
from project_network_analyzer.services.pipeline import analyze_network

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/analysis", response_model=AnalysisResponse)
def analysis(payload: NetworkIn) -> AnalysisResponse:
    """Validate the network and, when it is valid, analyse its structure."""
    network = build_network(payload)
    report = analyze_network(network)
    return AnalysisResponse(
        project=project_out(network),
        validation=ValidationOut.model_validate(report.validation),
        analysis=(
            AnalysisOut.model_validate(report.analysis)
            if report.analysis is not None
            else None
        ),
        findings=report.findings,
        report=report.text,
    )


@router.post("/interpretation", response_model=InterpretationResponse)
def interpretation(
    payload: InterpretationRequest, agent: LLMAgent = Depends(get_agent)
) -> InterpretationResponse:
    """
    Explain the deterministic report in plain language, and answer an
    optional question about it. The agent only ever sees the report text.
    """
    network = build_network(payload.network)
    report = analyze_network(network)
    answer = (
        agent.answer(payload.question, report.text)
        if payload.question
        else None
    )
    return InterpretationResponse(
        project=project_out(network),
        agent_mode=agent.mode,
        interpretation=agent.interpret(report.text),
        answer=answer,
        report=report.text,
    )


async def _network_structure_error(
    request: Request, exc: NetworkStructureError
) -> JSONResponse:
    """
    Report a domain rejection in the same shape FastAPI uses for its own
    validation errors, so clients parse one error format.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"type": "network_structure", "loc": ["body"], "msg": str(exc)}
            ]
        },
    )


async def _database_unavailable(
    request: Request, exc: OperationalError
) -> JSONResponse:
    """A configured database that cannot be reached is a 503, not a 500."""
    logger.warning("Database unavailable: %s", exc.orig)
    return JSONResponse(
        status_code=503, content={"detail": "The database is unavailable."}
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    if app.state.engine is not None:
        app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Build the application. Configuration is resolved here, once, so a bad
    PNA_MAX_TOKENS fails at startup rather than on the first request.
    Tests pass their own `settings` to pin the agent to fallback mode.

    Without a database URL the app still starts: the stateless endpoints
    work and the /networks ones answer 503.
    """
    settings = settings or load_settings()
    app = FastAPI(
        title="Project Network Analyzer",
        summary=(
            "Structural analysis of project networks modelled as directed "
            "acyclic graphs. The analysis is deterministic; the LLM only "
            "explains it."
        ),
        lifespan=_lifespan,
    )
    app.state.agent = LLMAgent(settings=settings)
    app.state.engine = (
        build_engine(settings.database_url) if settings.database_url else None
    )
    app.state.session_factory = (
        build_session_factory(app.state.engine) if app.state.engine else None
    )
    app.add_exception_handler(NetworkStructureError, _network_structure_error)
    app.add_exception_handler(OperationalError, _database_unavailable)
    app.include_router(router)
    app.include_router(networks.router)
    return app
