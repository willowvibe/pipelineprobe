# Architecture

This document explains how PipelineProbe's components fit together and how to extend them.

---

## High-Level Overview

```
┌──────────────────────────────────────────────────┐
│                       CLI                        │
│          audit · init · doctor · diff            │
└────────────────────────┬─────────────────────────┘
                         │  PipelineProbeConfig
                         ▼
┌──────────────────────────────────────────────────┐
│               Connectors Layer                   │
│  AirflowConnector   (Airflow REST API ≥ 2.0)    │
│  DbtConnector       (manifest.json / run_results)│
│  PostgresConnector  (pg_stat_user_tables)        │
│  BigQueryConnector  (INFORMATION_SCHEMA)         │
│  SnowflakeConnector (INFORMATION_SCHEMA + CTE)   │
└────────────────────────┬─────────────────────────┘
                         │  Dag, Task, DbtModel, TableStat dicts
                         ▼
┌──────────────────────────────────────────────────┐
│                  Rules Engine                    │
│  airflow_rules   dbt_rules   postgres_rules      │
└────────────────────────┬─────────────────────────┘
                         │  List[Issue]
                         ▼
┌──────────────────────────────────────────────────┐
│               Report Renderer                    │
│  Jinja2 HTML template  ·  json.dump              │
└────────────────────────┬─────────────────────────┘
                         │
                         ▼
               ./reports/
               pipelineprobe-report.html
               report.json
```

---

## Components

### CLI (`cli.py`)

Entry point registered as `pipelineprobe` via `pyproject.toml`. Uses [Typer](https://typer.tiangolo.com/).

**Commands:**

| Command | Description |
|---|---|
| `pipelineprobe init` | Write a default `pipelineprobe.yml` to the current directory |
| `pipelineprobe audit` | Full pipeline: load config → collect → run rules → render → exit with code 1 if threshold exceeded |
| `pipelineprobe doctor` | Validate connectivity to Airflow, dbt artifacts, and the warehouse without running a full audit |
| `pipelineprobe diff <a.json> <b.json>` | Compare two JSON reports; exit 1 if regressions found |

### Config (`config.py`)

Pydantic models backed by `pydantic-settings`. YAML values load first; environment variables override.

Key models:

| Model | Purpose |
|---|---|
| `AirflowConfig` | Airflow REST API URL, credentials, SSL, lookback window |
| `DbtConfig` | dbt project directory, manifest / run_results paths |
| `WarehouseConfig` | Warehouse type + credentials (dispatched at runtime) |
| `ReportConfig` | Output directory, format, fail_on_critical threshold |
| `RulesConfig` | Staleness threshold, fetch concurrency, per-rule severity overrides |

### Connectors (`connectors/`)

Each connector fetches raw data from one source and returns Python objects or dicts. All connectors catch exceptions internally and return an empty list on failure, ensuring a **partial report** is still produced when one source system is unavailable.

| Connector | Input | Output |
|---|---|---|
| `AirflowConnector` | Airflow REST API (paginated) | `List[Dag]`, `List[Task]` |
| `DbtConnector` | `manifest.json`, `run_results.json` | `List[DbtModel]` |
| `PostgresConnector` | `pg_stat_user_tables` + `information_schema` | `List[Dict]` |
| `BigQueryConnector` | `INFORMATION_SCHEMA.TABLE_STORAGE` + `COLUMNS` | `List[Dict]` |
| `SnowflakeConnector` | `INFORMATION_SCHEMA.TABLES` + CTE over `COLUMNS` | `List[Dict]` |

The Airflow connector uses `asyncio` to fetch DAG run history and task configs concurrently (controlled by `rules.fetch_concurrency`).

### Rules Engine (`rules/engine.py`, `rules/*_rules.py`)

`RuleEngine` is a simple registry of callable rule functions. Each rule receives a `context` dict and returns `List[Issue]`.

```python
context = {
    "airflow_dags":       [Dag, ...],
    "airflow_tasks":      [Task, ...],
    "dbt_models":         [DbtModel, ...],
    "warehouse_tables":   [{"tablename": ..., "row_count": ..., ...}, ...],
    "warehouse_type":     "postgres",
    "rule_severity_overrides": {...},
    "stale_threshold_days": 7,
}
```

Rules are registered at module import time via `register_*_rules(engine)`. New rules can be added without changing the engine itself — the engine is a stable extension point.

### Domain Models (`models.py`)

Pydantic models used throughout the pipeline:

| Model | Key Fields |
|---|---|
| `DagRun` | `state`, `start_time`, `end_time` |
| `Dag` | `id`, `is_active`, `recent_runs`, `owner` |
| `Task` | `dag_id`, `task_id`, `retries`, `sla`, `has_alerts` |
| `DbtModel` | `name`, `tests_count`, `last_run_status`, `tags` |
| `Issue` | `severity`, `category`, `summary`, `details`, `recommendation`, `affected_resources` |

### Report Renderer (`renderer.py`)

`ReportRenderer` accepts `List[Issue]` and a summary dict and produces:

- **`pipelineprobe-report.html`** — rendered via Jinja2 from `templates/report.html`
- **`report.json`** — serialized with `json.dump` and a custom `timedelta` handler

Before rendering HTML, the renderer computes:

- `top_actions` — the top 3 critical/warning issues sorted by severity then category
- `ring_offset` — SVG stroke-dashoffset for the health score ring (circumference 251.3 × (1 − score/100))

---

## Data Flow

```
audit()
  │
  ├─ load_config()            → PipelineProbeConfig
  │
  ├─ AirflowConnector
  │   ├─ get_dags()           → List[Dag]  (paginated, all pages)
  │   └─ fetch_dag_details()  → Dag.recent_runs + List[Task]  (concurrent)
  │
  ├─ DbtConnector
  │   └─ get_models()         → List[DbtModel]
  │
  ├─ WarehouseConnector
  │   └─ get_stats_sync()     → List[Dict]
  │
  ├─ RuleEngine.run(context)  → List[Issue]
  │
  ├─ compute summary
  │   score, critical_count, warning_count, info_count,
  │   total_issues, dag_count, score_formula, metadata
  │
  └─ ReportRenderer
      ├─ render_html()        → ./reports/pipelineprobe-report.html
      └─ render_json()        → ./reports/report.json
```

### Health Score Formula

```
critical_density = critical_count / dag_count
warning_density  = warning_count  / dag_count

critical_penalty = min(90, critical_density × 200)
warning_penalty  = min(20, warning_density  × 40)

score = max(0, round(100 − critical_penalty − warning_penalty))
```

Normalising by `dag_count` means five criticals in a 500-DAG platform is a very different signal from five criticals in a 10-DAG shop.

---

## Extending PipelineProbe

### Adding a Connector

1. Create `pipelineprobe/connectors/my_connector.py`.
2. Implement `get_stats_sync() -> List[Dict[str, Any]]` returning rows with `schemaname`, `tablename`, `row_count`, `has_timestamps`.
3. Route `cfg.warehouse.type == "my_connector"` in the `audit()` function in `cli.py`.
4. Add credentials to `WarehouseConfig` in `config.py`.
5. Document in `docs/configuration.md`.

### Adding a Rule

1. Write `def check_*(context: dict) -> List[Issue]` in the appropriate `rules/` file.
2. Call `engine.register_rule(check_*)` in the `register_*_rules` function.
3. Add a test in `tests/test_rules.py`.

### Modifying the HTML Report

The report template is `pipelineprobe/templates/report.html`. Template variables are documented in [CONTRIBUTING.md](../CONTRIBUTING.md#working-on-the-html-report). After editing, render a fresh report with `pipelineprobe audit` and inspect it in a browser.
