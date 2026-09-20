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
src/
├── modelo.py         Red class, structural validation
├── analizador.py     topological order, paths, σ(v), articulation points
├── visualizador.py   networkx + matplotlib render (Agg backend)
├── agente_ia.py      hybrid agent: rule layer + Claude API, with fallback
└── main.py           CLI orchestrator
tests/                41 tests, all passing, run without an API key
data/                 sample network: a 15-activity software project (A–O)
```

Run it: `python src/main.py`, output lands in `outputs/`.

## Where it is going

Roughly in this order. Each stage should leave the project working and tested.

1. **Restructure as a package.** `src/` flat modules → a proper package with
   domain / service / API layers separated. Rename identifiers to English as
   part of this; the test suite is the safety net.
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

## Conventions

- **Python 3.10+.** Type hints on anything crossing a module boundary.
- **English** for identifiers, docstrings, comments and commit messages. The
  original code is Spanish; translate it as you touch it, not in one sweep.
- **Deterministic code stays pure and testable.** No I/O, no network, no
  randomness inside the analysis functions.
- Secrets in `.env`, never in code. `.env.example` documents what is needed.
- New dependencies need a reason. This project is small; keep it that way.

## Working with the LLM layer

- Key: `ANTHROPIC_API_KEY` in `.env`.
- The model id is configuration, not a constant in the code. Current options:
  `claude-haiku-4-5-20251001` (cheap, fast — the default here) and
  `claude-sonnet-5` when output quality matters more than cost.
- **Fallback is a tested path, not a safety net nobody exercises.** The suite
  runs with no API key, and it must stay that way.
- Prompts belong in their own module, not inlined in business logic.

## Commands

```bash
python src/main.py                    # full run: analyse, render, report
python src/main.py --pregunta "..."   # ask the agent a question
pytest                                # the whole suite, no API key needed
```

## Guardrails

- Do not let the LLM into the analysis path.
- Do not widen the scope into time, cost or resources.
- Do not break the no-API-key path.
- Do not rewrite the graph algorithms to "simplify" them without checking the
  tests that verify dynamic programming and path enumeration agree.
