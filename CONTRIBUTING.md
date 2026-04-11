# Contributing to PipelineProbe

Thank you for your interest in contributing! PipelineProbe is an open-source project by [WillowVibe](https://www.willowvibe.com) and we welcome contributions of all kinds — bug reports, documentation improvements, new rules, and new connectors.

---

## Development Setup

### Prerequisites

- Python 3.11+
- `pip`
- A virtual environment tool (`venv`, `hatch`, `pyenv`, etc.)

### Clone and Install

```bash
git clone https://github.com/willowvibe/pipelineprobe.git
cd pipelineprobe

python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

pip install -e ".[dev]"
```

---

## Running Tests

```bash
pytest
```

Tests live in `tests/` and use `pytest`. Fixtures for mock data are in `tests/conftest.py`.

To run a specific file or test:

```bash
pytest tests/test_rules.py
pytest tests/test_renderer.py::test_render_html_no_issues
```

---

## Linting & Formatting

We use [ruff](https://docs.astral.sh/ruff/) for both linting and formatting:

```bash
ruff check .        # report lint errors
ruff check --fix .  # auto-fix safe issues
ruff format .       # format all files
```

CI fails if `ruff check .` reports any errors. Run both before opening a PR.

---

## Project Structure

```
pipelineprobe/
├── pipelineprobe/
│   ├── cli.py              # CLI entry points (audit, init, doctor, diff)
│   ├── config.py           # YAML + env var config loader (Pydantic)
│   ├── models.py           # Core domain models (Dag, Task, DbtModel, Issue)
│   ├── renderer.py         # HTML + JSON report renderer (Jinja2)
│   ├── connectors/
│   │   ├── airflow.py      # Apache Airflow REST API connector
│   │   ├── dbt.py          # dbt manifest / run_results reader
│   │   ├── postgres.py     # PostgreSQL INFORMATION_SCHEMA queries
│   │   ├── bigquery.py     # BigQuery INFORMATION_SCHEMA queries
│   │   └── snowflake.py    # Snowflake INFORMATION_SCHEMA queries
│   ├── rules/
│   │   ├── engine.py       # Pluggable rule registration and execution
│   │   ├── airflow_rules.py
│   │   ├── dbt_rules.py
│   │   └── postgres_rules.py
│   └── templates/
│       └── report.html     # Jinja2 HTML report template
├── tests/
│   ├── conftest.py         # Shared pytest fixtures
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_connectors.py
│   ├── test_renderer.py
│   └── test_rules.py
├── docs/
├── examples/
└── pyproject.toml
```

---

## Adding a New Rule

1. Add a function to the appropriate `rules/` module (e.g. `airflow_rules.py`):

```python
from typing import List
from pipelineprobe.models import Issue

def check_my_new_rule(context: dict) -> List[Issue]:
    issues = []
    for dag in context.get("airflow_dags", []):
        if some_condition(dag):
            issues.append(Issue(
                severity="warning",
                category="dag",
                summary="Short description of the problem",
                details="Longer explanation with context.",
                recommendation="Concrete steps to fix it.",
                affected_resources=[dag.id],
            ))
    return issues
```

2. Register it at the bottom of the same file:

```python
def register_airflow_rules(engine):
    ...
    engine.register_rule(check_my_new_rule)
```

3. Write tests in `tests/test_rules.py` — at minimum one happy-path and one edge-case test.

4. If the rule is configurable (e.g. severity override), document it in `docs/configuration.md` under the `rules.severity_overrides` table.

---

## Adding a New Connector

1. Create `pipelineprobe/connectors/my_connector.py`.
2. Implement a class with a `get_stats_sync() -> List[Dict[str, Any]]` method returning rows with at least: `schemaname`, `tablename`, `row_count`, `has_timestamps`.
3. Route `cfg.warehouse.type == "my_connector"` in the `audit()` function in `cli.py`.
4. Add any required credentials to `WarehouseConfig` in `config.py`.
5. Document the new connector and its config fields in `docs/configuration.md`.
6. Add at least one connectivity test in `tests/test_connectors.py`.

---

## Working on the HTML Report

The report template lives at `pipelineprobe/templates/report.html` and is rendered by `renderer.py` using Jinja2.

Variables available in the template:

| Variable | Type | Description |
|---|---|---|
| `issues` | `List[Issue]` | All findings from the rule engine |
| `summary` | `dict` | Health score, counts, dag_count, metadata |
| `top_actions` | `List[Issue]` | Top 3 critical/warning issues |
| `metadata` | `dict` | orchestrator_url, warehouse_type, dbt_target |
| `generated_at` | `str` | Formatted timestamp string |
| `version` | `str` | PipelineProbe version |
| `ring_offset` | `float` | SVG ring stroke-dashoffset (0 = full, 251.3 = empty) |

To preview a rendered report, run a real or mock audit and open `./reports/pipelineprobe-report.html` in a browser.

---

## Pull Request Process

1. Fork the repo and create your branch from `main`.
2. Write tests for your changes.
3. Ensure `ruff check .` and `pytest` both pass.
4. Open a PR with a description covering:
   - **What** changed
   - **Why** it is needed
   - **How** to test it manually

---

## Reporting Bugs

Open a GitHub Issue with:
- PipelineProbe version (`pip show pipelineprobe`)
- Python version
- A clear description of what happened vs. what you expected
- Sanitized config (no credentials) and relevant log output

---

## Code of Conduct

Be kind, constructive, and respectful. We follow the [Contributor Covenant](https://www.contributor-covenant.org/) Code of Conduct.
