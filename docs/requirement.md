Here is a complete requirements / tech-spec document for **PipelineProbe** as an OSS project you can start building immediately.

***

## 1. Product Overview

**Name:** PipelineProbe  
**Tagline:** *Instant Data Pipeline Audit Report for Airflow + dbt + modern warehouses*  
**Type:** OSS CLI + API + HTML report generator

### 1.1 Problem Statement

Small data teams inherit or grow complex pipelines (Airflow + dbt + warehouse) and cannot easily answer:

- Which DAGs/models are failing or flakiest?
- Where are SLAs missing or at risk?
- Which tables/queries are the main cost and performance offenders?
- Where are obvious best-practice gaps (no tests, no retries, no alerts)? [airflow.apache](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/logging-monitoring/check-health.html)

Existing observability tools either:

- Are SaaS and expensive (Monte Carlo, Databand, etc.), or
- Provide only low-level health endpoints (e.g., Airflow’s `/health`) and do not generate a human-readable audit report. [airflow.apache](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/logging-monitoring/check-health.html)

**PipelineProbe** = “one command, one report” for a **point-in-time audit** of data pipelines.

***

## 2. Goals & Non‑Goals

### 2.1 Goals (MVP)

1. **Connect** to an existing stack:  
   - Orchestrator: Apache Airflow (REST API + metadata DB)  
   - Transformations: dbt (local `manifest.json` and `run_results.json`)  
   - Warehouse: Postgres (Phase 1), BigQuery & Snowflake (Phase 2)
2. **Collect key metrics**:
   - DAG / task success & failure history
   - Missing retries / SLAs / alerts
   - Task runtimes (P50, P95)
   - dbt test coverage & failures
   - Basic warehouse table stats (row counts, last updated, scan volumes where possible)
3. **Produce an HTML/PDF report** with:
   - High-level summary (score / traffic-light style)
   - Critical issues, warnings, passes
   - Concrete recommendations with estimated impact / effort
4. **Ship as a CLI & Docker image** that can run locally or in CI.
5. **Be read-only and safe**: no mutations on orchestration or warehouse.

### 2.2 Non‑Goals (for MVP)

- Continuous monitoring or alerting (that’s ObservaKit’s job).
- Real-time UI/dashboard.
- Supporting every orchestrator/warehouse under the sun.
- Deep query-level tuning recommendations (e.g., auto-suggest SQL rewrites).

***

## 3. User Personas & Primary Flows

### 3.1 Personas

1. **Data Engineer / Analytics Engineer**
   - Owns Airflow/dbt pipelines.
   - Wants a quick health check before a big release or migration.
2. **Data Team Lead / Manager**
   - Needs an objective view of pipeline risk to plan refactors.
3. **Consultant (WillowVibe)**
   - Uses PipelineProbe as the **first step** in a paid Pipeline Audit engagement.

### 3.2 Primary User Flows

**Flow A: Local Audit (Developer)**
1. Install CLI: `pip install pipelineprobe`
2. Configure via YAML or flags (Airflow URL, dbt path, warehouse DSN).
3. Run:  
   ```bash
   pipelineprobe audit --config pipelineprobe.yml
   ```
4. Get `pipelineprobe-report.html` and optionally `report.json`.
5. Open in browser, share with team.

**Flow B: CI Audit (Consultant / Team Lead)**
1. Add GitHub Actions job or GitLab CI job.
2. Run `pipelineprobe audit` nightly or on-demand.
3. Archive HTML artifacts; optionally fail CI if critical issues > N.

***

## 4. Scope for MVP

### 4.1 Supported Systems (v0.1)

- **Orchestrator:** Apache Airflow
  - Airflow REST API (>=2.0) for DAG runs, task instances. [airflow.apache](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/logging-monitoring/check-health.html)
  - Optional direct DB access to `dag_run`, `task_instance` tables.
- **Transformations:** dbt Core
  - Read `target/manifest.json` and `target/run_results.json` to infer lineage and test coverage.
- **Warehouse:** PostgreSQL
  - Read `information_schema` and `pg_stat_all_tables` / simple queries for row counts & last updated.

### 4.2 Reports & Checks (MVP)

**1. DAG & Task Health**

- DAGs with:
  - High failure rate over last N runs (e.g., failure_ratio > 0.2).
  - No retries configured.
  - No SLA or no alert/email_on_failure configured.
- Longest-running tasks (P95 duration).
- DAGs with no recent successful runs (stale pipelines).

**2. dbt Project Health**

- Models with zero tests.
- Ratio of tests per model.
- Failing tests from last run (`run_results.json`).
- Orphans: models not referenced by any downstream model or exposure.

**3. Warehouse Surface Checks (Postgres)**

- Largest tables by row count.
- Tables with no `updated_at` / `created_at` column.
- Tables not partitioned (optional, Postgres specifics).

**4. Summary & Score**

- Overall “health score” (0–100) based on weighted issues.
- Count of:
  - Critical issues
  - Warnings
  - Passed checks

***

## 5. Architecture & Components

### 5.1 High-Level Architecture

```text
          +--------------+         +-----------------+
Airflow   |              |  API    |                 |
Metadata  |   Airflow    +-------->+  Probe Collector|
DB        |              |         |                 |
          +--------------+         +--------+--------+
                                           |
dbt       +--------------+                 |
Artifacts | manifest.json|                 v
          | run_results  |         +-----------------+
          +--------------+         |  Analyzer Core  |
                                   |  (rules engine) |
Warehouse +--------------+         +--------+--------+
(Postgres)| information_ |                 |
          | schema/tables|                 v
          +--------------+         +-----------------+
                                   |  Report Renderer|
                                   +-----------------+
                                            |
                                            v
                                    HTML / JSON report
```

**Core components:**
1. **Connectors layer**
   - `AirflowConnector`
   - `DbtConnector`
   - `PostgresConnector`
2. **Analyzer / Rules engine**
   - Normalizes raw data into internal models: `Dag`, `Task`, `Model`, `Table`.
   - Runs a set of rules → produces `Issue` objects.
3. **Report Renderer**
   - Jinja2 templates to generate HTML.
   - Optional JSON for programmatic consumption.
4. **CLI & Config**
   - CLI entrypoint using `typer` or `click`.
   - YAML config loader with sane defaults.

***

## 6. Tech Stack

### 6.1 Backend & CLI

- **Language:** Python 3.11+
- **CLI:** `typer` (or `click`) for a modern CLI UX.
- **HTTP Client:** `httpx` (async-capable) for Airflow REST.
- **DB Access:**
  - `asyncpg` or `psycopg2` for Postgres.
  - Use SQLAlchemy core for portability if you plan to add other warehouses later.
- **Config:** `pydantic-settings` or `pydantic` for typed config models.
- **Templating:** `jinja2` for HTML report templates.
- **Packaging:** `pyproject.toml` with `hatchling` or `poetry` / standard `build`.

### 6.2 Optional API Service (Later)

- **Framework:** FastAPI (reuses your ObservaKit experience).
- Purpose: expose `/audit` endpoint to run audit on-demand and return JSON.

### 6.3 Frontend (Later Phase)

- MVP: static HTML + TailwindCSS / minimal custom CSS.
- Later: React/Vite front-end that consumes the JSON if you want a hosted UI.

### 6.4 Deployment

- **CLI:** `pip install pipelineprobe`.
- **Container:** Docker image with:
  - Python base
  - `pipelineprobe` installed
  - Entry point: `pipelineprobe audit`

***

## 7. Configuration Design

### 7.1 YAML Config Example

```yaml
# pipelineprobe.yml

orchestrator:
  type: airflow
  base_url: "http://localhost:8080"
  username: "admin"
  password: "admin"
  verify_ssl: false
  lookback_days: 14

dbt:
  project_dir: "./analytics"
  target: "prod"
  manifest_path: "target/manifest.json"
  run_results_path: "target/run_results.json"

warehouse:
  type: postgres
  dsn: "postgresql://user:pass@localhost:5432/analytics"

report:
  output_dir: "./reports"
  format: "html"        # html | json | both
  include_cost_section: false
  fail_on_critical: 5   # exit code != 0 if >5 critical issues
```

### 7.2 Environment Variables (for secrets)

- `PIPELINEPROBE_AIRFLOW_PASSWORD`
- `PIPELINEPROBE_WAREHOUSE_DSN`

Config loader: values from YAML, overridden by env vars.

***

## 8. Data Model & Rule Engine

### 8.1 Core Domain Models

```python
class Dag(BaseModel):
    id: str
    is_active: bool
    recent_runs: list[DagRun]
    owner: str | None

class DagRun(BaseModel):
    state: str  # success/failed/running
    start_time: datetime
    end_time: datetime | None

class Task(BaseModel):
    dag_id: str
    task_id: str
    retries: int
    sla: timedelta | None
    has_alerts: bool

class DbtModel(BaseModel):
    name: str
    tests_count: int
    last_run_status: str  # success/failed
    tags: list[str]

class Issue(BaseModel):
    severity: Literal["critical", "warning", "info"]
    category: Literal["dag", "task", "dbt", "warehouse"]
    summary: str
    details: str
    recommendation: str
    affected_resources: list[str]
```

### 8.2 Example Rules

**Rule: DAG with high failure ratio**

- Input: Dag with last N runs.
- Condition: `failed_runs / total_runs > 0.2` and `total_runs >= 5`.
- Output: `Issue(severity="critical", category="dag", ...)`.

**Rule: Task with no retries**

- Condition: `task.retries == 0`.
- Severity: `warning` unless failure ratio high → `critical`.

**Rule: dbt model with no tests**

- Condition: `tests_count == 0`.
- Severity: `warning`.

**Rule: Stale DAG**

- Condition: no successful run in last N days.

***

## 9. Report Structure

### 9.1 HTML Layout

1. **Header**
   - Project name, date, version.
   - Target environment (Airflow URL, dbt target, warehouse).
2. **Executive Summary**
   - Score (0–100).
   - Number of DAGs, tasks, models, tables scanned.
   - Critical / Warning / Info counts.
3. **Sections**
   - DAG Health
     - Table of DAGs with failure rates, staleness, owner.
   - Task Config Review
     - Tasks missing retries, SLAs, alerts.
   - dbt Project Health
     - Tests per model, failing tests, orphan models.
   - Warehouse Overview (Postgres)
     - Largest tables, candidates for partitioning.
4. **Recommendations**
   - Prioritized list (impact x effort).

### 9.2 JSON Output

Machine-readable representation of:
- `issues: [Issue, ...]`
- `summary: { score, counts... }`

For integration into CI or other tools (including ObservaKit).

***

## 10. Non‑Functional Requirements

- **Performance:**  
  - Target: audit a small–mid stack (≤100 DAGs, ≤200 dbt models) in < 2 minutes.
- **Security:**  
  - Read-only connections.  
  - No secrets logged.  
  - Redact DSNs and credentials from reports.
- **Reliability:**  
  - If one connector fails (e.g., dbt missing), still produce partial report with clear note.
- **Portability:**  
  - Runs on Linux/macOS/WSL.  
  - Python 3.11+.
- **Extensibility:**  
  - New connectors (Prefect, Dagster) can be added under a common interface.
  - Rules engine defined as pluggable classes / functions.

***

## 11. Milestones & Phases

### Phase 0 — Design & Skeleton (1 week)

- Create repo: `willowvibe/PipelineProbe`.
- Set up `pyproject.toml`, CI (lint + tests), basic CLI that just prints config.

### Phase 1 — Airflow + dbt + Postgres (3–4 weeks)

- Implement connectors:
  - Airflow API client.
  - dbt manifest/run_results reader.
  - Postgres table stats.
- Implement 8–10 core rules.
- Implement HTML renderer (Jinja2 template, Tailwind or simple CSS).
- Ship v0.1.0 to PyPI + Docker Hub.

### Phase 2 — DX & CI Integration (2 weeks)

- Add GitHub Actions example workflow.
- Add JSON output and `fail_on_critical` flag.
- Improve docs with real screenshots.

### Phase 3 — New Integrations (ongoing)

- BigQuery connector (query `INFORMATION_SCHEMA.JOBS` etc.). [atlan](https://atlan.com/open-source-data-quality-tools/)
- Snowflake connector (`QUERY_HISTORY`).
- Prefect/Dagster connectors if demand appears.

***

If you want, next step I can turn this into:

- A checklist-style GitHub issue template for `PipelineProbe` repo, and
- An initial `README.md` + `pyproject.toml` skeleton you can paste and push to start coding immediately.