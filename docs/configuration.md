# Configuration Reference

This document describes every configuration option supported by PipelineProbe, including `pipelineprobe.yml` YAML fields, environment variable overrides, and CLI flags.

---

## Quick Example

```yaml
orchestrator:
  type: airflow
  base_url: "http://airflow.internal:8080"
  username: "admin"
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
  format: "both"
  fail_on_critical: 5

rules:
  stale_threshold_days: 7
  fetch_concurrency: 10
```

> **Tip** — Run `pipelineprobe init` to generate this file with defaults in your current directory.

---

## `orchestrator` — Airflow Connection

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | string | `"airflow"` | Connector type. Only `"airflow"` is supported in v0.1. |
| `base_url` | string | `"http://localhost:8080"` | Base URL for the Airflow REST API. |
| `username` | string | `"admin"` | Airflow username. |
| `password` | string | `"admin"` | Airflow password. **Prefer the env var** `PIPELINEPROBE_AIRFLOW_PASSWORD`. |
| `verify_ssl` | boolean | `false` | Whether to verify TLS certificates. Set to `true` in production. |
| `lookback_days` | integer | `14` | Days of DAG run history to fetch for analysis. |

### Environment Variable

| Variable | Overrides |
|---|---|
| `PIPELINEPROBE_AIRFLOW_PASSWORD` | `orchestrator.password` |

---

## `dbt` — dbt Core Artifacts

| Field | Type | Default | Description |
|---|---|---|---|
| `project_dir` | string | `"./analytics"` | Root directory of the dbt project. |
| `target` | string | `"prod"` | dbt target name (informational — used for report labelling). |
| `manifest_path` | string | `"target/manifest.json"` | Path to `manifest.json` relative to `project_dir`. |
| `run_results_path` | string | `"target/run_results.json"` | Path to `run_results.json` relative to `project_dir`. |

> **Note** — If `manifest.json` does not exist, the dbt connector is skipped gracefully and the report will note its absence. No error is raised.

---

## `warehouse` — Warehouse Connection

The `type` field selects which connector is used. Each warehouse type has its own set of required fields.

### PostgreSQL

```yaml
warehouse:
  type: postgres
  dsn: "postgresql://user:password@host:5432/dbname"
```

| Field | Description |
|---|---|
| `type` | Must be `"postgres"` |
| `dsn` | Full PostgreSQL DSN string. **Prefer the env var** `PIPELINEPROBE_WAREHOUSE_DSN`. |

### BigQuery

```yaml
warehouse:
  type: bigquery
  project_id: "my-gcp-project"
```

| Field | Description |
|---|---|
| `type` | Must be `"bigquery"` |
| `project_id` | GCP project ID. If omitted, falls back to the default project from ADC. |

Authentication is handled via [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials). Set `GOOGLE_APPLICATION_CREDENTIALS` to the path of a service account JSON key, or use `gcloud auth application-default login` locally.

### Snowflake

```yaml
warehouse:
  type: snowflake
  account: "xyz.us-east-1"
  username: "my_user"
  password: "my_password"
```

| Field | Description |
|---|---|
| `type` | Must be `"snowflake"` |
| `account` | Snowflake account identifier (e.g. `xyz.us-east-1`). |
| `username` | Snowflake user. |
| `password` | Snowflake password. Store in a secret manager or CI secret rather than in the YAML. |

### Environment Variables

| Variable | Overrides |
|---|---|
| `PIPELINEPROBE_WAREHOUSE_DSN` | `warehouse.dsn` (PostgreSQL only) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to BigQuery service account JSON key |

---

## `report` — Output Settings

| Field | Type | Default | Description |
|---|---|---|---|
| `output_dir` | string | `"./reports"` | Directory where reports are written. Created automatically if missing. |
| `format` | string | `"html"` | Output format: `html`, `json`, or `both`. Can be overridden with `--format`. |
| `include_cost_section` | boolean | `false` | Reserved for a future cost analysis section. Has no effect in v0.1. |
| `fail_on_critical` | integer | `5` | Return exit code `1` when critical issue count **exceeds** this value. Set to `0` to fail on any single critical issue. Can be overridden with `--fail-on-critical`. |

---

## `rules` — Rule Engine Settings

| Field | Type | Default | Description |
|---|---|---|---|
| `stale_threshold_days` | integer | `7` | Number of days without a successful DAG run before it is flagged as stale. |
| `fetch_concurrency` | integer | `10` | Maximum concurrent Airflow API calls when fetching DAG run history and task configs. |
| `severity_overrides` | dict | `{}` | Per-rule severity overrides. See table below. |

### `severity_overrides`

Override the default severity of any built-in rule. Valid values are `critical`, `warning`, or `info`.

```yaml
rules:
  severity_overrides:
    missing_sla: critical        # default: info   — raise to critical for SLA-sensitive teams
    missing_retries: warning     # default: warning — no change needed
    stale_dags: critical         # default: warning — raise to critical for prod monitors
    high_failure_rate: critical  # default: critical
```

| Rule key | Default severity | Description |
|---|---|---|
| `missing_retries` | `warning` | Tasks with zero retries configured |
| `missing_slas` | `info` | Tasks without an SLA timeout |
| `high_failure_rate` | `critical` | DAGs with >20% failure rate over ≥5 runs |
| `stale_dags` | `warning` | Active DAGs with no successful run in `stale_threshold_days` |
| `missing_tests` | `warning` | dbt models with zero tests |
| `failing_models` | `critical` | dbt models that failed their last run |
| `large_tables` | `warning` | Tables with >10M rows |
| `missing_timestamps` | `warning` | Tables >1M rows without `created_at` / `updated_at` |

---

## CLI Flags

All flags are passed to `pipelineprobe audit`:

```bash
pipelineprobe audit \
  --config path/to/pipelineprobe.yml \
  --format both \
  --fail-on-critical 3
```

| Flag | Equivalent Config | Description |
|---|---|---|
| `--config FILE` | — | Path to the YAML config file. |
| `--format FORMAT` | `report.format` | Override report format: `html`, `json`, or `both`. |
| `--fail-on-critical N` | `report.fail_on_critical` | Override the critical issue threshold. |

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Audit completed; critical count at or below `fail_on_critical` |
| `1` | Critical count exceeds threshold, or a config / connectivity error occurred |

---

## Security Best Practices

1. **Never store passwords in `pipelineprobe.yml` when committing to source control.** Use environment variables or a secrets manager instead.
2. `pipelineprobe.yml` is listed in `.gitignore` by default — verify it is in place before your first commit.
3. PipelineProbe is **strictly read-only** — it never writes to Airflow, dbt, or your warehouse.
4. DSN strings and passwords are never written to any report output (HTML or JSON).
