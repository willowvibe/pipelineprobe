# Configuration Reference

This document describes every configuration option supported by PipelineProbe, including the `pipelineprobe.yml` YAML fields and recognised environment variables.

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
```

> **Tip**: Run `pipelineprobe init` to generate this file with defaults in your current directory.

---

## `orchestrator` — Airflow Connection

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | string | `"airflow"` | Connector type. Only `"airflow"` is supported in v0.1. |
| `base_url` | string | `"http://localhost:8080"` | Base URL for the Airflow REST API. |
| `username` | string | `"admin"` | Airflow username. |
| `password` | string | `"admin"` | Airflow password. **Prefer the env var** `PIPELINEPROBE_AIRFLOW_PASSWORD`. |
| `verify_ssl` | boolean | `false` | Whether to verify TLS certificates. Set to `true` in production. |
| `lookback_days` | integer | `14` | Number of days of DAG run history to fetch for analysis. |

### Environment Variable Override

| Variable | Overrides |
|---|---|
| `PIPELINEPROBE_AIRFLOW_PASSWORD` | `orchestrator.password` |

---

## `dbt` — dbt Core Artifacts

| Field | Type | Default | Description |
|---|---|---|---|
| `project_dir` | string | `"./analytics"` | Root directory of the dbt project. |
| `target` | string | `"prod"` | dbt target name (informational only, used for labelling). |
| `manifest_path` | string | `"target/manifest.json"` | Path to `manifest.json` **relative to `project_dir`**. |
| `run_results_path` | string | `"target/run_results.json"` | Path to `run_results.json` relative to `project_dir`. |

> **Note**: If `manifest.json` does not exist, the dbt connector is skipped gracefully and the report will note the absence. No error is raised.

---

## `warehouse` — Warehouse Connection

The `type` field selects which connector is used.

### PostgreSQL

```yaml
warehouse:
  type: postgres
  dsn: "postgresql://user:password@host:5432/dbname"
```

| Field | Description |
|---|---|
| `type` | Must be `"postgres"` |
| `dsn` | A full PostgreSQL DSN string. **Prefer the env var** `PIPELINEPROBE_WAREHOUSE_DSN`. |

### BigQuery

```yaml
warehouse:
  type: bigquery
  project_id: "my-gcp-project"
```

| Field | Description |
|---|---|
| `type` | Must be `"bigquery"` |
| `project_id` | GCP project ID. If omitted, the default project from `GOOGLE_APPLICATION_CREDENTIALS` or ADC is used. |

Authentication is handled via [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials). Set the `GOOGLE_APPLICATION_CREDENTIALS` env var to the path of a service account JSON key.

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
| `password` | Snowflake password. |

### Environment Variable Override

| Variable | Overrides |
|---|---|
| `PIPELINEPROBE_WAREHOUSE_DSN` | `warehouse.dsn` (PostgreSQL only) |

---

## `report` — Output Settings

| Field | Type | Default | Description |
|---|---|---|---|
| `output_dir` | string | `"./reports"` | Directory where reports are written. Created automatically if missing. |
| `format` | string | `"html"` | Output format: `html`, `json`, or `both`. Can be overridden via `--format` CLI flag. |
| `include_cost_section` | boolean | `false` | Reserved for a future cost analysis section. Has no effect in v0.1. |
| `fail_on_critical` | integer | `5` | Non-zero exit code is returned if the number of critical issues **exceeds** this value. Set to `0` to fail on any single critical issue. Can be overridden via `--fail-on-critical` CLI flag. |

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
| `--config` | N/A | Path to the YAML config file. |
| `--format` | `report.format` | Override the report output format. |
| `--fail-on-critical` | `report.fail_on_critical` | Override the critical issue threshold. |

---

## Security Best Practices

1. **Never store passwords in `pipelineprobe.yml` when committing to source control.** Use environment variables instead.
2. `.pipelineprobe.yml` is listed in `.gitignore` by default. Verify this is in place.
3. PipelineProbe is **read-only** — it never writes to Airflow, dbt, or your warehouse.
4. DSN strings and passwords are never written to report output.
