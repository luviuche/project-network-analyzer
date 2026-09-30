"""
schemas.py — The HTTP contract, as Pydantic models.

Request models check the SHAPE of the payload: types, required fields,
a non-empty activity list. Structural rules — duplicate ids, unknown
predecessors, cycles — stay in the domain, which is their single source
of truth; the API reports what the domain decides instead of repeating
those checks here.

Response models mirror the domain's result objects field by field and
read them through `from_attributes`, so no value is recomputed on the
way out.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------- #


class ActivityIn(BaseModel):
    """One activity and the activities that must finish before it."""

    id: str = Field(min_length=1, examples=["B"])
    name: str | None = Field(
        default=None, description="Defaults to the id.", examples=["Design"]
    )
    description: str = ""
    predecessors: list[str] = Field(default_factory=list, examples=[["A"]])


class ProjectIn(BaseModel):
    name: str | None = Field(default=None, description='Defaults to "network".')
    description: str = ""


class NetworkIn(BaseModel):
    """A project network: the same format as the JSON files the CLI reads."""

    project: ProjectIn | None = None
    activities: list[ActivityIn] = Field(min_length=1)

    def to_domain_dict(self) -> dict:
        """
        The payload in the shape `Network.from_dict` takes. Unset optional
        fields are dropped so the domain applies its own defaults.
        """
        return self.model_dump(exclude_none=True)


class InterpretationRequest(BaseModel):
    network: NetworkIn
    question: str | None = Field(
        default=None,
        description="An open question about the network, answered from the report.",
    )


# --------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------- #


class ProjectOut(BaseModel):
    name: str
    description: str


class ValidationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool
    is_acyclic: bool
    is_weakly_connected: bool
    sources: list[str]
    sinks: list[str]
    detected_cycle: list[str]


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topological_order: list[str]
    path_count: int
    paths: list[list[str]]
    paths_truncated: bool
    centrality: dict[str, int] = Field(description="σ(v) per activity.")
    critical_nodes: list[str] = Field(description="V* = argmax σ(v).")
    max_sigma: int
    bottlenecks: list[str]
    articulation_points: list[str]
    initial: list[str]
    final: list[str]
    intermediate: list[str]
    generations: list[list[str]]


class AnalysisResponse(BaseModel):
    project: ProjectOut
    validation: ValidationOut
    analysis: AnalysisOut | None = Field(
        description="Null when the network fails validation."
    )
    findings: list[str]
    report: str


class InterpretationResponse(BaseModel):
    project: ProjectOut
    agent_mode: str
    interpretation: str
    answer: str | None = Field(description="Null when no question was asked.")
    report: str = Field(description="The deterministic report the agent was given.")


class HealthResponse(BaseModel):
    status: str
