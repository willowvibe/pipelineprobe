# Architecture

This document explains how PipelineProbe's components fit together.

---

## High-Level Overview

```
                       +-----------+
        pipelineprobe  |    CLI    |  audit / init
                       +-----------+
                             |
                     loads   |  PipelineProbeConfig
                             v
          +------------------------------------+
          |         Connectors Layer          |
          |  AirflowConnector  (REST API)     |
          |  DbtConnector      (JSON files)   |
          |  PostgresConnector (asyncpg)      |
          |  BigQueryConnector (google-cloud) |
          |  SnowflakeConnector(sf.connector) |
          +------------------------------------+
                             |
                  returns    |  Dag, Task, DbtModel, TableStat dicts
                             v
          +------------------------------------+
          |           Rules Engine            |
          |  airflow_rules  dbt_rules         |
          |  postgres_rules   ...             |
          +------------------------------------+
                             |
                   emits     |  List[Issue]
                             v
          +------------------------------------+
          |         Report Renderer           |
          |   Jinja2 HTML template            |
          |   json.dump  report.json          |
          +------------------------------------+
                             |
                    writes   |
                             v
                    ./reports/
                    pipelineprobe-report.html
                    report.json
```

---

## Components

### CLI (`cli.py`)

Entry point registered as `pipelineprobe` via `pyproject.toml`. Uses [Typer](https://typer.tiangolo.com/).

**Commands:**
- `pipelineprobe init` — writes a default `pipelineprobe.yml` to the current directory.
- `pipelineprobe audit` — runs the full pipeline: load config → collect data → run rules → render reports → exit with code 1 if critical threshold exceeded.

### Config (`config.py`)

Pydantic models backed by `pydantic-settings`. YAML values are loaded first; environment variables take precedence.

Key models:
- `AirflowConfig`
- `DbtConfig`
- `WarehouseConfig` — type-dispatched at runtime in `cli.py`
- `ReportConfig`

### Connectors (`connectors/`)

Each connector is responsible for fetching raw data from one source system and returning Python dicts or domain model objects.

| Connector | Input | Output |
|---|---|---|
| `AirflowConnector` | Airflow REST API | `List[Dag]`, `List[Task]` |
| `DbtConnector` | `manifest.json`, `run_results.json` | `List[DbtModel]` |
| `PostgresConnector` | `pg_stat_user_tables` + `information_schema` | `List[Dict]` |
| `BigQueryConnector` | `INFORMATION_SCHEMA.TABLE_STORAGE` + `COLUMNS` | `List[Dict]` |
| `SnowflakeConnector` | `INFORMATION_SCHEMA.TABLES` + CTE over `COLUMNS` | `List[Dict]` |

All connectors catch exceptions internally and return an empty list on failure, ensuring a **partial report** is still produced when one source system is unavailable.

### Rules Engine (`rules/engine.py`, `rules/*_rules.py`)

The `RuleEngine` is a simple registry of callable rule functions. Each rule receives a `context` dict and returns `List[Issue]`.

```python
context = {
    "airflow_dags":  [Dag, ...],
    "airflow_tasks": [Task, ...],
    "dbt_models":    [DbtModel, ...],
    "postgres_tables": [{"tablename": ..., "row_count": ..., ...}, ...],
}
```

Rules are registered at module import time via `register_*_rules(engine)`. New rules can be added without changing the engine itself — the engine is a stable extension point.

### Domain Models (`models.py`)

Pydantic models used throughout:

| Model | Fields |
|---|---|
| `DagRun` | `state`, `start_time`, `end_time` |
| `Dag` | `id`, `is_active`, `recent_runs`, `owner` |
| `Task` | `dag_id`, `task_id`, `retries`, `sla`, `has_alerts` |
| `DbtModel` | `name`, `tests_count`, `last_run_status`, `tags` |
| `Issue` | `severity`, `category`, `summary`, `details`, `recommendation`, `affected_resources` |

### Report Renderer (`renderer.py`)

`ReportRenderer` accepts `List[Issue]` + a summary dict and produces:
- `pipelineprobe-report.html` via Jinja2 (`templates/report.html`)
- `report.json` via `json.dump` with a custom serializer for non-standard types (e.g. `timedelta`)

---

## Data Flow

```
audit()
  │
  ├─ load_config()          → PipelineProbeConfig
  │
  ├─ AirflowConnector
  │   ├─ get_dags()         → List[Dag]  (paginated)
  │   ├─ get_dag_runs(id)   → Dag.recent_runs populated
  │   └─ get_tasks(id)      → List[Task]
  │
  ├─ DbtConnector
  │   └─ get_models()       → List[DbtModel]
  │
  ├─ WarehouseConnector
  │   └─ get_stats_sync()   → List[Dict]
  │
  ├─ RuleEngine.run(context)→ List[Issue]
  │
  ├─ compute summary (score, counts)
  │
  └─ ReportRenderer
      ├─ render_html()      → ./reports/pipelineprobe-report.html
      └─ render_json()      → ./reports/report.json
```

---

## Extending PipelineProbe

### Adding a Connector

1. Create `pipelineprobe/connectors/my_connector.py`.
2. Implement `get_stats_sync() -> List[Dict[str, Any]]` returning rows with `schemaname`, `tablename`, `row_count`, `has_timestamps`.
3. Route `cfg.warehouse.type == "my_connector"` in `cli.py`.
4. Add credentials to `WarehouseConfig` in `config.py`.

### Adding a Rule

1. Write `def check_*(context: dict) -> List[Issue]` in the appropriate `rules/` file.
2. Call `engine.register_rule(check_*)` in the `register_*_rules` function.
3. Add a test in `tests/test_rules.py`.
