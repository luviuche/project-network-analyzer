# Project Network Analyzer

Structural analysis of project networks modelled as directed acyclic graphs,
with a hybrid agent that explains the results in plain language.

## What it does

A project plan is modelled as a DAG, analysed by deterministic code, and the
result is handed to an LLM that puts it into words. The sample case is the
structural planning of a software project.

- Builds the activity DAG from precedence relations.
- Validates the structural properties: acyclicity, weak connectivity, and the
  existence of a source node and a sink node.
- Computes the topological order.
- Enumerates the source→sink paths.
- Identifies structurally critical activities (path centrality).
- Detects articulation points (hard structural bottlenecks).
- Classifies activities: initial, final, intermediate and parallel.
- Produces a report, interpreted by the agent.

> **Scope:** strictly structural. Durations, float, cost and resource
> allocation are deliberately out of scope. The analysis is sharp because it
> is narrow.

### The model

Let `G = (V, E)` be a directed acyclic graph where `V` are the activities and
`E ⊆ V × V` the precedence relations. The central question is:

```
V* = argmax_{v ∈ V} σ(v)
```

where `σ(v)` is the number of source→sink paths running through `v`. The
nodes in `V*` are the **structurally critical** ones.

`σ(v)` is computed by dynamic programming over the topological order in
O(|V| + |E|), which avoids enumerating paths in order to count them. The
test suite cross-checks the DP against exhaustive enumeration.

### The hybrid agent

1. **Rule layer** (`services/report.py`): turns the analyser's numbers into a
   structured report. Fully deterministic, no API key needed.
2. **LLM layer** (`agent/llm_agent.py`): takes that report as context and
   writes the natural-language explanation, or answers open questions.

**The LLM never computes anything.** Every number, path and classification
comes from deterministic code covered by tests. With no API key, or on a
failed connection, the agent runs in **fallback mode** and the system still
produces the complete report. That path is tested rather than assumed: the
whole suite runs without a key.

The separation is structural rather than a convention — `agent/` imports
nothing from `domain/`, so there is nothing there for it to compute with.

## Requirements

- Python 3.10 or later.
- Dependencies are declared in `pyproject.toml`: `networkx`, `matplotlib`,
  `anthropic`, `python-dotenv`, and `pytest` for the tests.

## Installation

```bash
# 1. Clone the repository and enter it
git clone git@github.com:luviuche/project-network-analyzer.git
cd project-network-analyzer

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Install the project and its dependencies (editable)
pip install -e ".[dev]"

# 4. Configure the API key (optional — without it the agent falls back)
cp .env.example .env
# edit .env and replace the ANTHROPIC_API_KEY value
```

## Usage

```bash
pna
```

Equivalent: `python -m project_network_analyzer`.

This will:

1. Load the sample case from `data/software_project.json`.
2. Build and validate the network.
3. Run the full structural analysis.
4. Render the graph to `outputs/network_graph.png`.
5. Write the interpreted report to `outputs/report.txt`.

Options:

```bash
pna --data data/other_network.json   # analyse a different network
pna --question "Which node is the most critical?"
pna --model claude-sonnet-5          # change the LLM layer's model
```

### Input format

A network is a JSON document listing its activities and, for each one, the
activities that must finish before it can start:

```json
{
  "project": {"name": "My project", "description": "Optional."},
  "activities": [
    {"id": "A", "name": "Requirements", "predecessors": []},
    {"id": "B", "name": "Design", "predecessors": ["A"]}
  ]
}
```

Only `id` is required. A missing `name` falls back to the id, a missing
`predecessors` means the activity is a starting one, and activities may be
listed in any order.

Configuration comes from the environment (see `.env.example`):
`ANTHROPIC_API_KEY`, `PNA_MODEL` and `PNA_MAX_TOKENS`.

To run the tests — no API key and no install needed:

```bash
pytest
```

## Project layout

```
project-network-analyzer/
├── CLAUDE.md                    # Project context and working guide
├── README.md                    # This file
├── pyproject.toml               # Packaging, dependencies and pytest config
├── requirements.txt             # Shortcut pointing at pyproject.toml
├── .env.example                 # Environment variable template
├── data/
│   └── software_project.json    # Sample case: web app, 15 activities
├── src/project_network_analyzer/
│   ├── domain/                  # Pure: no I/O, no network, no randomness
│   │   ├── errors.py            # NetworkStructureError
│   │   ├── network.py           # Network class and structural validation
│   │   └── analysis.py          # Paths, centrality, articulation points
│   ├── services/
│   │   └── report.py            # Rule layer: the deterministic report
│   ├── agent/
│   │   ├── llm_agent.py         # LLM layer (Claude API) with fallback
│   │   └── prompts.py           # Prompts for the LLM layer
│   ├── infrastructure/
│   │   ├── loader.py            # The only place that reads the JSON
│   │   └── rendering.py         # Graph drawing (networkx + matplotlib)
│   ├── config.py                # LLM layer configuration
│   ├── cli.py                   # Orchestrator
│   └── __main__.py              # python -m project_network_analyzer
├── tests/                       # 64 tests, all passing without an API key
│   ├── test_cli.py
│   ├── test_config.py
│   ├── domain/                  # Model and analyser
│   ├── services/                # Rule layer
│   ├── agent/                   # Agent in fallback mode
│   └── infrastructure/          # Loader and rendering
└── outputs/                     # Generated output (graph and report)
```

## The sample case

`data/software_project.json` models the development of a task-management web
application: 15 activities (A–O), from requirements gathering to project
close. It has parallel branches — architecture design against UI/UX,
integration against unit testing — which is what makes the structural
analysis worth running.

The expected results are pinned in the test suite: 12 source→sink paths,
critical nodes V* = {A, B, N, O} with σ = 12, and articulation points B and N.

## Origin

Built as the final project for a university Operations Research course. It
is now being rebuilt as a deployed backend service. The domain logic carries over; the
delivery around it is what changes. `CLAUDE.md` holds the roadmap.
