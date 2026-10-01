# Project Network Analyzer

A backend that models a project plan as a directed acyclic graph, analyses its
structure, and has an LLM explain the result in plain language.

## The one rule

**The LLM never computes anything.** It receives the analyser's output and puts
it into words. Every number, path and classification comes from deterministic
code that is covered by tests. If the model is unavailable, the system still
produces a full report from the rule-based layer.

This is the point of the project, not a limitation of it. Any change that lets
the model influence the analysis is wrong, however convenient.

## Where this stands

The analysis core is complete and tested. The work now is turning it into a
deployed backend service: the domain logic is sound and should be carried
over; the delivery around it is what changes.

## Domain model

G = (V, E), a directed acyclic graph where V are activities and E are
precedence relations.

Invariants the model validates:

1. Acyclic — no directed cycle.
2. Weakly connected.
3. At least one source node (in-degree 0).
4. At least one sink node (out-degree 0).

The central question: find V* = argmax σ(v), where σ(v) is the number of
source→sink paths through v. Those are the structurally critical activities.

**Scope is structural only** — path counts, centrality, articulation points,
topological order, activity classification. Deliberately *not* durations,
float, cost or resource allocation. Keep it that way: the analysis is sharp
because it is narrow.

## Current state

```
src/project_network_analyzer/
├── domain/                pure: imports only dataclasses and networkx
│   ├── errors.py          NetworkStructureError
│   ├── network.py         Network, ValidationResult, from_dict
│   └── analysis.py        topological order, paths, σ(v), articulation points
├── services/
│   ├── report.py          rule layer: structured report, no API key needed
│   └── pipeline.py        validate → analyse → report, shared by the API
├── api/                   HTTP boundary: translates, computes nothing
│   ├── app.py             create_app(), /health, /analysis, /interpretation
│   ├── networks.py        /networks: save, list, fetch, interpretations
│   ├── shared.py          dependencies: agent, DB session
│   └── schemas.py         Pydantic models: shape checks only
├── agent/                 the only layer that calls the API
│   ├── llm_agent.py       LLM layer with fallback; imports nothing from domain
│   └── prompts.py         system prompt and instructions
├── infrastructure/
│   ├── loader.py          the only place that reads the JSON from disk
│   ├── rendering.py       networkx + matplotlib render (Agg backend)
│   └── db/                SQLAlchemy models, session, repository
├── config.py              settings resolved from the environment
├── cli.py                 CLI orchestrator
└── __main__.py            python -m project_network_analyzer
migrations/           Alembic; the only way the schema changes
tests/                143 tests, no API key needed; 36 need PostgreSQL
data/                 sample network: a 15-activity software project (A–O)
```

Everything is English: code, docs, the report, error messages, the chart,
the CLI, and the JSON data format (`project`, `activities`, `predecessors`).
Output goes to `outputs/`.

## Where it is going

Roughly in this order. Each stage should leave the project working and tested.

1. ~~**Restructure as a package.**~~ Done. The flat modules became a layered
   package, identifiers are English, file I/O left the domain, the agent split
   into a rule service and an LLM layer, and the project is installable.
2. ~~**FastAPI on top.**~~ Done. `/analysis` is deterministic and never calls
   the LLM; only the interpretation endpoints reach the agent.
   Pydantic checks the payload's shape; structural rules stay in the domain.
   An unbuildable network is a 422; a built but invalid one is a 200 whose
   answer is the validation result.
3. ~~**PostgreSQL.**~~ Done. Networks are saved with their analyses
   (`/networks`), through Alembic migrations rather than `create_all`. The
   LLM's interpretations are saved too, one row per model reply, about the
   STORED report; a fallback notice is returned but never saved.
4. **Rework the agent.** Keep the two-layer design and the fallback. Consider
   tool-calling so the model can request specific analyses rather than being
   handed one blob of context — but the tools stay deterministic.
5. **Docker + deploy.** Containerise, then put it somewhere reachable. A live
   URL is worth more than another local project.

Testing is not a stage. Every layer gets tests as it lands.

Known, deliberately deferred:

- The sample network is not packaged into the wheel, so an installed `pna`
  needs a `data/` directory in the working directory. Irrelevant under Docker,
  where the repo is copied in.
- The API accepts networks of any size. Path enumeration is capped at
  `PATH_LIMIT`, but a very large network still means a very large response.
  A request size limit belongs with the deploy stage.
- The chart legend sits at `lower center` and covers the bottom row of nodes
  when a phase is wide (in the sample case: D, G, I, K).

## Conventions

- **Python 3.10+.** Type hints on anything crossing a module boundary.
- **English, everywhere.** Identifiers, docstrings, comments, commit messages
  and every user-facing string. The project started out in Spanish and was
  translated in full; one language keeps the API contract coherent.
- **Deterministic code stays pure and testable.** No I/O, no network, no
  randomness inside the analysis functions.
- Secrets in `.env`, never in code. `.env.example` documents what is needed.
- New dependencies need a reason. This project is small; keep it that way.

## Working with the LLM layer

- Configuration lives in `config.py`, resolved by `load_settings()`:
  `ANTHROPIC_API_KEY` (absent or left as the `.env.example` placeholder ->
  fallback), `PNA_MODEL` and `PNA_MAX_TOKENS`. Explicit arguments beat the
  environment, which beats the defaults.
- The model id is configuration, not a constant in the code. Current options:
  `claude-haiku-4-5-20251001` (cheap, fast — the default here) and
  `claude-sonnet-5` when output quality matters more than cost.
- `domain/` reads nothing from the environment. Its one tunable,
  `StructuralAnalyzer.PATH_LIMIT`, is an algorithmic safeguard rather than a
  deployment knob, and keeping it a plain constant is what keeps the domain
  pure.
- **Fallback is a tested path, not a safety net nobody exercises.** The suite
  runs with no API key, and it must stay that way.
- Prompts belong in their own module, not inlined in business logic.

## Working with the database

- **The schema changes only through Alembic.** Edit `infrastructure/db/models.py`,
  then `alembic revision --autogenerate`, then read and tidy the result. A
  test fails when models and migrations disagree.
- Structural rules live in the domain, which runs before anything is saved.
  The database repeats what it can express (unique keys, same-network
  foreign keys, no self-precedence) as a second line of defence.
- Saved networks are immutable, so their stored analysis never goes stale.
  `position` columns keep declaration order, which the rebuilt graph needs
  to report the same cycle.
- The repository never commits; the caller owns the transaction.
- `PNA_DATABASE_URL` is optional: without it the API starts and `/networks`
  answers 503. An unreachable database is also a 503, not a 500.
- Response timestamps are converted to UTC at the API boundary, whatever
  time zone the PostgreSQL server uses.
- Database tests use `PNA_TEST_DATABASE_URL` and skip without it. The name
  must end in `_test`: the fixture drops and rebuilds the schema.

## Commands

```bash
pip install -e ".[dev]"   # once; requirements.txt points at pyproject.toml

pna                       # full run: analyse, render, report
pna --question "..."      # ask the agent a question
pna --data other.json     # analyse a different network

pytest                    # the whole suite, no API key needed

alembic upgrade head      # apply migrations to PNA_DATABASE_URL
uvicorn --factory project_network_analyzer.api.app:create_app   # the API
```

`python -m project_network_analyzer` is equivalent to `pna`. The suite also
runs straight from a fresh clone with no install, because
`[tool.pytest.ini_options]` keeps `pythonpath = ["src"]`.

Installed as a wheel rather than in editable mode, the CLI resolves `data/`
and `outputs/` against the working directory, since its own location is then
inside site-packages. The sample network is not shipped in the wheel.

## Guardrails

- Do not let the LLM into the analysis path.
- Do not widen the scope into time, cost or resources.
- Do not break the no-API-key path.
- Do not rewrite the graph algorithms to "simplify" them without checking the
  tests that verify dynamic programming and path enumeration agree.
