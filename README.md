# PipelineProbe

> *Instant Data Pipeline Audit Report for Airflow + dbt + modern warehouses*

[![CI](https://github.com/willowvibe/pipelineprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/willowvibe/pipelineprobe/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

PipelineProbe is a **read-only, one-command audit tool** for data pipelines. It connects to your existing stack — Apache Airflow, dbt, and a modern warehouse — and produces a single actionable HTML or JSON report surfacing critical issues, missing SLAs, missing tests, high failure rates, and more.

It is open-sourced by [WillowVibe](https://www.willowvibe.com).

---

## ✨ Features

| Area | What it checks |
|---|---|
| **Airflow** | DAG failure rates, missing retries, missing SLAs, stale pipelines, alert configuration |
| **dbt** | Models with zero tests, test failure ratio, failing last runs |
| **Warehouse** | Largest tables, tables missing audit timestamps (`created_at`/`updated_at`) |
| **Report** | Health score (0–100), critical / warning / info counts, HTML + JSON output |

---

## 🚀 Quick Start

### 1. Install

```bash
pip install pipelineprobe
```

### 2. Initialize a config file

```bash
pipelineprobe init
```

This creates `pipelineprobe.yml` in the current directory.

### 3. Run an audit

```bash
pipelineprobe audit --config pipelineprobe.yml
```

Reports are written to `./reports/` by default.

---

## ⚙️ Configuration

See [docs/configuration.md](docs/configuration.md) for the full reference. A minimal example:

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
  # for BigQuery: project_id: "my-gcp-project"
  # for Snowflake: account: "xyz.us-east-1", username: "...", password: "..."

report:
  output_dir: "./reports"
  format: "html"          # html | json | both
  fail_on_critical: 5
```

### CLI Flags

| Flag | Description |
|---|---|
| `--config` | Path to config YAML (default: `pipelineprobe.yml`) |
| `--format` | Override output format: `html`, `json`, or `both` |
| `--fail-on-critical` | Override the critical issue threshold for CI exits |

---

## 🔌 Supported Integrations

| Connector | Status |
|---|---|
| Apache Airflow (REST API ≥ 2.0) | ✅ Supported |
| dbt Core (manifest + run_results) | ✅ Supported |
| PostgreSQL | ✅ Supported |
| BigQuery | ✅ Supported |
| Snowflake | ✅ Supported |

---

## 🤖 CI/CD Integration

PipelineProbe can automatically fail your CI pipeline when critical issues exceed your threshold. See [docs/ci-integration.md](docs/ci-integration.md) for GitHub Actions and GitLab CI examples.

---

## 🖼️ Report Preview

![PipelineProbe HTML Report Screenshot](docs/report-screenshot.png)

---

## 📖 Documentation

| Document | Description |
|---|---|
| [Configuration Reference](docs/configuration.md) | All YAML and environment variable options |
| [CI Integration Guide](docs/ci-integration.md) | GitHub Actions, GitLab CI, fail-on-critical |
| [Architecture](docs/architecture.md) | How connectors, rules, and the renderer fit together |
| [Contributing](CONTRIBUTING.md) | Development setup, testing, PRs |
| [Changelog](CHANGELOG.md) | Release history |

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
