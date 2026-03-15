# Contributing to PipelineProbe

Thank you for your interest in contributing! PipelineProbe is an open-source project by [WillowVibe](https://www.willowvibe.com) and we welcome contributions of all kinds, including bug reports, documentation improvements, and new connectors.

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

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

# Install in editable mode with all dev dependencies
pip install -e ".[dev]"
```

---

## Running Tests

```bash
pytest
```

Tests live in the `tests/` directory and use `pytest`. Fixtures for mock data are in `tests/conftest.py`.

---

## Linting

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .       # Check for lint errors
ruff check --fix . # Auto-fix safe issues
ruff format .      # Format code
```

CI will fail if `ruff check .` reports any errors.

---

## Project Structure

```
pipelineprobe/
├── pipelineprobe/
│   ├── cli.py            # CLI entry points (audit, init)
│   ├── config.py         # YAML + env var config loader (Pydantic)
│   ├── models.py         # Core domain models (Dag, Task, DbtModel, Issue)
│   ├── renderer.py       # HTML + JSON report renderer (Jinja2)
│   ├── connectors/
│   │   ├── airflow.py    # Apache Airflow REST API connector
│   │   ├── dbt.py        # dbt manifest / run_results reader
│   │   ├── postgres.py   # PostgreSQL INFORMATION_SCHEMA queries
│   │   ├── bigquery.py   # BigQuery INFORMATION_SCHEMA queries
│   │   └── snowflake.py  # Snowflake INFORMATION_SCHEMA queries
│   ├── rules/
│   │   ├── engine.py     # Pluggable rule registration and execution
│   │   ├── airflow_rules.py
│   │   ├── dbt_rules.py
│   │   └── postgres_rules.py
│   └── templates/
│       └── report.html   # Jinja2 HTML report template
├── tests/
├── docs/
├── examples/
└── pyproject.toml
```

---

## Adding a New Rule

1. Add a function to the appropriate `rules/` module (e.g. `airflow_rules.py`):

```python
def check_my_new_rule(context: dict) -> List[Issue]:
    issues = []
    for dag in context.get("airflow_dags", []):
        # Your logic here
        if some_condition:
            issues.append(Issue(
                severity="warning",
                category="dag",
                summary="...",
                details="...",
                recommendation="...",
                affected_resources=[dag.id]
            ))
    return issues
```

2. Register it at the bottom of the same file:

```python
def register_airflow_rules(engine):
    ...
    engine.register_rule(check_my_new_rule)
```

3. Write a test in `tests/test_rules.py`.

---

## Adding a New Connector

1. Create `pipelineprobe/connectors/my_connector.py`.
2. Implement a class with a `get_stats_sync() -> List[Dict[str, Any]]` method that returns rows with `schemaname`, `tablename`, `row_count`, and `has_timestamps`.
3. Add your new warehouse type to `cli.py` in the `if cfg.warehouse.type ==` block.
4. Add any required credentials to `WarehouseConfig` in `config.py`.
5. Document it in `docs/configuration.md`.

---

## Pull Request Process

1. Fork the repo and create your branch from `main`.
2. Write tests for your changes (aim for at least one happy-path and one edge-case test).
3. Ensure `ruff check .` and `pytest` both pass.
4. Open a Pull Request with a clear description of:
   - **What** changed
   - **Why** it's needed
   - **How** to test it manually

---

## Reporting Bugs

Please open a GitHub Issue with:
- PipelineProbe version (`pip show pipelineprobe`)
- Python version
- A description of the bug and what you expected to happen
- Sanitized config (no credentials) and any relevant log output

---

## Code of Conduct

Be kind, constructive, and respectful. We follow the [Contributor Covenant](https://www.contributor-covenant.org/) Code of Conduct.
