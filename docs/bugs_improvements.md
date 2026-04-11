# Bugs & Improvements Tracker

This file tracks known issues, planned improvements, and the current state of each item.

---

## Completed

### Report UI
- [x] Add "Top 3 actions to take" summary section — implemented in renderer and template.
- [x] Include environment metadata (Airflow URL, warehouse type, dbt target) in the report header.
- [x] Add a "generated with PipelineProbe vX.Y.Z" footer.
- [x] Add an Info count card alongside Critical and Warnings in the summary grid.
- [x] SVG animated health-score ring replacing the plain numeric display.
- [x] Severity filter buttons (All / Critical / Warnings / Info) on the findings list.
- [x] Affected resource tags shown on each finding card.
- [x] Subtle per-severity background tints on issue cards.
- [x] Responsive layout and print CSS.

### CLI & DX
- [x] `pipelineprobe doctor` command — validates connectivity to Airflow, dbt artifacts, and the warehouse.
- [x] `pipelineprobe diff` command — compares two JSON reports and surfaces regressions / improvements with coloured output and exit code 1 on regression.
- [x] `--version` flag.
- [x] `--format` validation with clear error on unsupported values.
- [x] `--fail-on-critical` documented in README and CI guide.
- [x] Exit codes documented (`0` = success, `1` = threshold breached or error).

### Bug Fixes
- [x] Airflow connector pagination — organisations with >100 DAGs no longer receive silently truncated results.
- [x] `check_stale_dags` — correctly flags active DAGs with zero recorded runs.
- [x] `BigQueryConnector.has_timestamps` — was hardcoded `True`; now queries `INFORMATION_SCHEMA.COLUMNS`.
- [x] `SnowflakeConnector` — correlated subquery replaced with a CTE; empty-credential early return added.
- [x] `renderer.render_json()` — `TypeError` on `timedelta` serialization fixed.
- [x] All bare `print()` replaced with `logging.getLogger(__name__)`.
- [x] PostgreSQL connector uses `try/finally` to guarantee connection closure.

### Docs
- [x] README overhauled: quick start, CLI reference table, exit codes, diff workflow, comparison table.
- [x] CONTRIBUTING.md updated: template variable reference, rule/connector extension guide.
- [x] docs/architecture.md updated: diff command, ring_offset, health score formula.
- [x] docs/configuration.md updated: `rules` section, `severity_overrides` table, exit codes.
- [x] docs/ci-integration.md updated: `diff` regression detection workflow, threshold guide, exit codes.
- [x] CHANGELOG.md: proper version comparison links added.

---

## Open / Planned

### v0.2.0 — Connectors
- [x] Prefect connector — `pipelineprobe/connectors/prefect.py`; maps flows/runs to shared Dag/DagRun models; Prefect Cloud auth via `orchestrator.api_key`.
- [x] Dagster connector — `pipelineprobe/connectors/dagster.py`; queries Dagster GraphQL API; groups runs by job name; Dagster Cloud auth via `orchestrator.api_key`.

### v0.3.0 — Cost Insights
- [x] BigQuery: top tables by scanned bytes — `BigQueryConnector.get_cost_insights_sync()` queries `INFORMATION_SCHEMA.JOBS_BY_PROJECT`; `check_expensive_bq_tables` rule (warning ≥ 500 GiB, critical ≥ 5 TiB).
- [x] Snowflake: credit consumption per warehouse — `SnowflakeConnector.get_cost_insights_sync()` queries `WAREHOUSE_METERING_HISTORY`; `check_snowflake_credit_spenders` rule (warning ≥ 500, critical ≥ 5 000 credits).

### v1.0.0 — Lineage
- [ ] Basic data lineage support (upstream/downstream DAG relationships).

### Quickstart
- [ ] Harden the Docker Compose quickstart: add a minimal toy dbt project with models and `run_results.json` so new users get a fully populated HTML report out of the box.

### Release Hygiene
- [ ] Tag `v0.1.0` GitHub release.
- [ ] Publish to PyPI so `pip install pipelineprobe` resolves to the correct package.
