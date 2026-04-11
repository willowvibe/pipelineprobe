# Changelog

All notable changes to PipelineProbe are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **Report UI overhaul** — sticky topbar, animated SVG health-score ring, severity filter buttons (All / Critical / Warnings / Info), affected-resource tags on each finding card, subtle per-severity background tints, and responsive print styles.
- **Info count card** — the summary grid now shows a fourth card for informational findings alongside Critical and Warnings.
- `info_count` included in the JSON report summary for downstream tooling.
- `ring_offset` computed in the renderer and injected into the Jinja2 template so the SVG ring accurately reflects the health score.
- BigQuery connector querying `INFORMATION_SCHEMA.TABLE_STORAGE` and `COLUMNS` for real `has_timestamps` detection.
- Snowflake connector using a CTE pattern to work around correlated subquery restrictions.
- `python-dateutil` declared as an explicit dependency in `pyproject.toml`.

### Fixed
- `pipelineprobe audit --format` was shadowing Python's built-in `format()`. Renamed CLI parameter to `report_format` internally.
- Added validation to `--format` — passing unsupported values (e.g. `csv`) now exits with a clear error.
- `get_dags()` in the Airflow connector now paginates correctly. Previously, organisations with more than 100 DAGs would silently receive truncated results.
- `check_stale_dags` now correctly flags active DAGs that have **zero recorded runs** (previously silently skipped).
- Double-space indentation bug in `check_stale_dags` fixed.
- `BigQueryConnector` was returning `has_timestamps = True` for every table (hardcoded). Now queries actual `INFORMATION_SCHEMA.COLUMNS`.
- `SnowflakeConnector` was silently connecting with empty string credentials. Now validates and returns early with a log error.
- `SnowflakeConnector` correlated subquery replaced with a CTE, which is supported by Snowflake's `INFORMATION_SCHEMA`.
- `affected_resources` in warehouse rules could contain `None` when `tablename` was absent. Now falls back to `"<unknown>"`.
- `renderer.render_json()` raised `TypeError` when `Task.sla` (`timedelta`) was serialized. Added `_json_default` handler.
- `test_cli_init` was failing if a `pipelineprobe.yml` already existed in the project root. Test now uses a temporary directory.
- All bare `print()` error statements replaced with `logging.getLogger(__name__)` across all modules.
- PostgreSQL connector now uses `try/finally` to guarantee `conn.close()` is called even on errors.

---

## [0.1.0] — 2026-03-15

### Added
- **Phase 0** — Project skeleton, `pyproject.toml`, CI workflow (ruff + pytest), CLI entry point.
- **Phase 1 — MVP connectors:**
  - `AirflowConnector` — fetches DAGs, DAG runs, and task configurations via the Airflow REST API.
  - `DbtConnector` — reads `manifest.json` and `run_results.json`; counts tests per model.
  - `PostgresConnector` — queries `pg_stat_user_tables` and `information_schema.columns`.
- **Phase 1 — Rules Engine:**
  - `check_missing_retries` — warns on tasks with no retry configuration.
  - `check_missing_slas` — informs on tasks with no SLA.
  - `check_high_failure_rate` — critical alert for DAGs with >20% failure rate over ≥5 runs.
  - `check_stale_dags` — warns on active DAGs with no successful run in 7+ days.
  - `check_missing_tests` — warns on dbt models with zero tests.
  - `check_failing_models` — critical alert for dbt models that failed their last run.
  - `check_large_tables` — warns on tables with >10M rows.
  - `check_missing_timestamps` — warns on tables >1M rows without `created_at`/`updated_at`.
- **Phase 1 — Report Renderer** — Jinja2 HTML template; JSON output via `model_dump()`.
- **Phase 2 — DX & CI:**
  - `pipelineprobe init` command generating a default `pipelineprobe.yml`.
  - `--fail-on-critical` and `--format` CLI overrides.
  - `examples/github-actions/pipelineprobe.yml` GitHub Actions workflow.
  - `docs/ci-integration.md`.
  - `.gitignore` with standard Python exclusions.
- **Phase 3 — Extended Integrations:**
  - `BigQueryConnector`.
  - `SnowflakeConnector`.
  - `pipelineprobe doctor` command for connectivity validation.
  - `pipelineprobe diff` command for regression detection between two JSON reports.

---

[Unreleased]: https://github.com/willowvibe/pipelineprobe/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/willowvibe/pipelineprobe/releases/tag/v0.1.0
