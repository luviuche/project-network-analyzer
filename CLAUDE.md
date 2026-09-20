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

## Where this came from

Built as the final project for a university Operations Research course
(structural analysis of project networks). That version is complete: 41 passing
tests, a CLI, a rendered graph and a text report.

It is now being rebuilt as a deployed backend service, as the capstone of a
Backend + Applied AI specialisation. The domain logic is sound and should be
carried over; the delivery around it is what changes.

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
│   └── report.py          rule layer: structured report, no API key needed
├── agent/                 the only layer that calls the API
│   ├── llm_agent.py       LLM layer with fallback; imports nothing from domain
│   └── prompts.py         system prompt and instructions
├── infrastructure/
│   ├── loader.py          the only place that reads the JSON from disk
│   └── rendering.py       networkx + matplotlib render (Agg backend)
├── config.py              LLM settings resolved from the environment
├── cli.py                 CLI orchestrator
└── __main__.py            python -m project_network_analyzer
tests/                63 tests, all passing, run without an API key
data/                 sample network: a 15-activity software project (A–O)
```

Identifiers, docstrings and comments are English. What stays Spanish is
user-facing: the report text, error messages, the chart legend, the CLI
flags and console output, and the JSON payload keys (`proyecto`,
`actividades`, `precedentes`) — that last one is the data format, not
the code. Output goes to `outputs/`.

## Where it is going

Roughly in this order. Each stage should leave the project working and tested.

1. ~~**Restructure as a package.**~~ Done. The flat modules became a layered
   package, identifiers are English, file I/O left the domain, the agent split
   into a rule service and an LLM layer, and the project is installable.
2. **FastAPI on top.** Expose the analysis over HTTP: submit a network, get the
   structural report. Pydantic models for validation at the boundary.
3. **PostgreSQL.** Persist networks and their analyses instead of reading a
   JSON file each run. Migrations, not `create_all`.
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
- `load_network` propagates `json.JSONDecodeError` for a malformed file rather
  than wrapping it in `NetworkStructureError` the way a missing file is. Worth
  settling when the HTTP boundary lands and needs one error type.

## Conventions

- **Python 3.10+.** Type hints on anything crossing a module boundary.
- **English** for identifiers, docstrings, comments and commit messages. The
  original code is Spanish; translate it as you touch it, not in one sweep.
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

## Commands

```bash
pip install -e ".[dev]"   # once; requirements.txt points at pyproject.toml

pna                       # full run: analyse, render, report
pna --pregunta "..."      # ask the agent a question
pna --datos otra.json     # analyse a different network

pytest                    # the whole suite, no API key needed
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
