# PipelineProbe

> *Instant Data Pipeline Audit — Airflow · dbt · modern warehouses*

[![CI](https://github.com/willowvibe/pipelineprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/willowvibe/pipelineprobe/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pipelineprobe.svg)](https://pypi.org/project/pipelineprobe/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

PipelineProbe is a **read-only, one-command audit tool** for data pipelines. It connects to your existing stack — Apache Airflow, dbt, and a modern warehouse — and produces a single actionable HTML or JSON report surfacing critical issues, missing SLAs, failing tests, high failure rates, and more.

Open-sourced by [WillowVibe](https://www.willowvibe.com).

---

## Features

| Area | What it checks |
|---|---|
| **Airflow** | DAG failure rates, missing retries, missing SLAs, stale pipelines, alert configuration |
| **dbt** | Models with zero tests, failing last runs |
| **Warehouse** | Largest tables, tables missing audit timestamps (`created_at` / `updated_at`) |
| **Report** | Health score (0–100), critical / warning / info counts, severity filter, HTML + JSON output |

---

## Quick Start

### 1. Install

```bash
pip install pipelineprobe
```

### 2. Create a config file

```bash
pipelineprobe init
```

This writes `pipelineprobe.yml` to the current directory with sensible defaults.

### 3. Run an audit

```bash
pipelineprobe audit --config pipelineprobe.yml
```

Reports are written to `./reports/` by default — open `pipelineprobe-report.html` in any browser.

### 5-Minute Docker Quickstart

Want to see it in action without a local stack?

```bash
cd examples/quickstart
docker compose up --build
```

See [examples/quickstart/README.md](examples/quickstart/README.md) for details.

---

## Configuration

A minimal `pipelineprobe.yml`:

```yaml
orchestrator:
  base_url: "http://localhost:8080"
  username: "admin"
  # password via env: PIPELINEPROBE_AIRFLOW_PASSWORD

dbt:
  project_dir: "./analytics"
  manifest_path: "target/manifest.json"
  run_results_path: "target/run_results.json"

warehouse:
  type: postgres         # postgres | bigquery | snowflake
  dsn: "postgresql://user:pass@localhost:5432/analytics"

report:
  output_dir: "./reports"
  format: "html"          # html | json | both
  fail_on_critical: 5
```

See [docs/configuration.md](docs/configuration.md) for the full reference including BigQuery, Snowflake, and all rule-level options.

---

## CLI Reference

### Commands

| Command | Description |
|---|---|
| `pipelineprobe init` | Write a default `pipelineprobe.yml` to the current directory |
| `pipelineprobe audit` | Run the full audit and generate reports |
| `pipelineprobe doctor` | Validate connectivity to Airflow, dbt, and the warehouse before auditing |
| `pipelineprobe diff <a.json> <b.json>` | Compare two JSON reports and surface regressions / improvements |

### `audit` flags

| Flag | Default | Description |
|---|---|---|
| `--config FILE` | `pipelineprobe.yml` | Path to config YAML |
| `--format FORMAT` | from config | Override output format: `html`, `json`, or `both` |
| `--fail-on-critical N` | from config | Override critical issue threshold for non-zero exit |
| `--version` | — | Print version and exit |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Audit completed; critical count at or below threshold |
| `1` | Critical issue count exceeds `fail_on_critical`, or a config / connectivity error occurred |

### Examples

```bash
# Basic local audit
pipelineprobe audit

# CI strict mode: fail if even one critical issue is found
pipelineprobe audit --format both --fail-on-critical 0

# Compare today's report against yesterday's baseline
pipelineprobe diff reports/baseline.json reports/report.json

# Check connectivity without running the full audit
pipelineprobe doctor --config staging.yml

# Print version
pipelineprobe --version
```

---

## Supported Integrations

| Connector | Status |
|---|---|
| Apache Airflow (REST API ≥ 2.0) | Supported |
| dbt Core (manifest + run_results) | Supported |
| PostgreSQL | Supported |
| BigQuery | Supported |
| Snowflake | Supported |

---

## Standard Workflows

### 1. Local Audit

Identify issues before they reach production. Run `pipelineprobe audit` on a dev machine or before merging infrastructure changes.

```bash
pipelineprobe init
# edit pipelineprobe.yml with your Airflow URL, dbt paths, and warehouse DSN
pipelineprobe audit --format html
# open ./reports/pipelineprobe-report.html
```

### 2. CI Quality Gate

Fail your build when critical issues surface. Use `--fail-on-critical 0` for zero-tolerance enforcement. See [docs/ci-integration.md](docs/ci-integration.md).

```bash
pipelineprobe audit --format both --fail-on-critical 0
```

### 3. Regression Detection with `diff`

Compare successive audit reports to catch new issues introduced between runs:

```bash
pipelineprobe audit --format json     # generates report.json
# ... later / next CI run ...
pipelineprobe diff reports/baseline.json reports/report.json
# exits 1 if regressions found
```

### 4. Consulting / One-off Audits

Connect to a client's stack, run the audit, and deliver the polished HTML report as a professional-grade artefact.

---

## How PipelineProbe Differs from Other Tools

| Feature | Monitoring (Datadog, Monte Carlo) | Quality Libraries (Soda, Great Expectations) | **PipelineProbe** |
|---|---|---|---|
| **Focus** | Continuous alerting & dashboards | Row-level data validation | Infrastructure & config audit |
| **Effort to start** | High — install agents, configure SDKs | Medium — write YAML expectations | **Zero — read-only, no agents** |
| **Output** | Dashboards, alerts | Pass / fail per expectation | **Single HTML / JSON report** |
| **Best for** | On-call engineers | Data engineers | **Consultants · Team leads · CI gates** |

---

## CI/CD Integration

PipelineProbe can automatically fail your CI pipeline when critical issues exceed your threshold. See [docs/ci-integration.md](docs/ci-integration.md) for ready-to-use GitHub Actions and GitLab CI configs.

---

## Documentation

| Document | Description |
|---|---|
| [Configuration Reference](docs/configuration.md) | All YAML fields, environment variables, and rule-level options |
| [CI Integration Guide](docs/ci-integration.md) | GitHub Actions, GitLab CI, `diff` regression detection |
| [Architecture](docs/architecture.md) | How connectors, rules, and the renderer fit together |
| [Contributing](CONTRIBUTING.md) | Development setup, testing, adding rules and connectors |
| [Changelog](CHANGELOG.md) | Release history |

---

## Roadmap

- [ ] **v0.2.0** — Prefect and Dagster connectors
- [ ] **v0.3.0** — Cost insights (scanned bytes for BigQuery / Snowflake)
- [ ] **v1.0.0** — Data lineage support

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) to get started. All contributions are welcome — bug reports, docs, new rules, new connectors.

## License

MIT — see [LICENSE](LICENSE) for details.
