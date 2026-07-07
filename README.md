# Overview

This repository contains the source code for a research framework that investigates how different configurations of LLM-based multi-agent pipelines affect code generation quality. The system runs a benchmark of 339 programming tasks through various agent configurations and evaluates the results on feature coverage and code quality.


## Architecture

All agents are built on an OpenAI-compatible API client with automatic retry and token/latency tracking. Workflows are orchestrated with [LangGraph](https://github.com/langchain-ai/langgraph).

### Agent Roles

| Agent | Responsibility |
|---|---|
| **Planner** | Converts a task description into a structured implementation plan |
| **Architect** | Converts a plan into a software architecture design (components, interfaces, data flow) |
| **Programmer** | Implements code; mode-aware (solo, plan-guided, architecture-guided, review-fix, test-fix) |
| **Reviewer** | Reviews code against the task spec; triggers revision cycles if needed |
| **Tester** | Writes and executes unit tests in a sandboxed environment; triggers fix cycles on failure |

### Graph Configurations

| Graph name | Pipeline |
|---|---|
| `solo_programmer` | Programmer |
| `planner_programmer` | Planner → Programmer |
| `programmer_reviewer` | Programmer ⇄ Reviewer |
| `programmer_tester` | Programmer ⇄ Tester |
| `plan_programmer_reviewer` | Planner → Programmer ⇄ Reviewer |
| `plan_programmer_tester` | Planner → Programmer ⇄ Tester |
| `planner_architect_programmer` | Planner → Architect → Programmer |
| `planner_architect_programmer_reviewer` | Planner → Architect → Programmer ⇄ Reviewer |
| `planner_architect_programmer_reviewer_tester` | Planner → Architect → Programmer ⇄ Reviewer ⇄ Tester |

In graphs with both Reviewer and Tester, code is reviewed first; test failures route directly back to the Programmer.

## Installation

**Requirements:** Python 3.11+, conda


Set your API credentials via environment variables (do not hardcode keys):

```bash
export OPENAI_API_KEY=your_api_key
export BASE_URL=
export MODEL_NAME=
```

## Usage

### Run the Full Experiment

Runs all 5 primary graph configurations across all tasks, then evaluates results:

```bash
conda run -n mastesting python run_experiment.py
```

Optional flags:

| Flag | Effect |
|---|---|
| `--skip-run` | Skip code generation, reuse existing outputs |
| `--skip-judge` | Skip LLM feature coverage evaluation |
| `--skip-static` | Skip pylint static analysis |
| `--graphs solo_programmer planner_programmer` | Run only the specified graphs |


### Configuration

All settings are read from environment variables. Key options:

| Variable | Default | Description |
|---|---|---|
| `MODEL_NAME` | `""` | LLM model identifier |
| `BASE_URL` | `""` | API base URL |
| `OPENAI_API_KEY` | `""` | API key |
| `MODEL_TEMPERATURE` | `0.0` | Sampling temperature |
| `GRAPH_NAME` | `programmer_reviewer` | Agent graph to run |
| `OUTPUT_ROOT` | `outputs/` | Output directory root |
| `MAX_REVIEWER_ITERATIONS` | `5` | Max review–fix cycles per task |
| `MAX_TESTER_ITERATIONS` | `5` | Max test–fix cycles per task |
| `MAX_RETRIES` | `3` | Retries on graph-level failure |


## Task File

Tasks are defined in `multiAgent/Task/feature-final.json`:

```json
{
  "task_1": {
    "task": "Write a Python script that ...",
    "features": ["feature 1", "feature 2"],
    "type": "Data scraping"
  }
}
```


## Project Structure

```
├── run_experiment.py              # Top-level experiment orchestrator
├── multiAgent/
│   ├── run_all.py                 # CLI entry point
│   ├── batch_runner.py            # Batch run logic and manifest management
│   ├── config/
│   │   ├── setting.py             # Global settings (env vars)
│   │   └── models.py              # Registered model configs
│   ├── state/schema.py            # LangGraph state schemas
│   ├── agents/                    # Agent implementations
│   ├── graphs/                    # LangGraph workflow definitions
│   ├── prompt/                    # System prompts for each agent role
│   ├── utils/code_executor.py     # Sandboxed Python test runner
│   └── Task/feature-final.json    # 339 benchmark tasks
├── LLMasJudge/
│   └── calcFeature.py             # 3-model LLM judge for feature coverage
└── staticAnalysis/
    └── analysis.py                # Pylint-based static analysis
```
