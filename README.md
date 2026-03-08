# PipelineProbe

*Instant Data Pipeline Audit Report for Airflow + dbt + modern warehouses*

PipelineProbe is a "one command, one report" tool for generating point-in-time audits of data pipelines. It is designed to connect to your existing stack (Airflow, dbt, Postgres) and produce an actionable HTML or JSON report identifying critical issues, missing SLAs, missing tests, and more.

## Installation

```bash
pip install pipelineprobe
```

## Usage

```bash
# Run an audit locally
pipelineprobe audit --config pipelineprobe.yml
```

### Configuration Example
To control failure thresholds and targets, create `pipelineprobe.yml`:

```yaml
report:
  output_dir: "./reports"
  format: "html"
  fail_on_critical: 2
```

> [!NOTE] Placeholder for Screenshot
> *A screenshot of the PipelineProbe Dashboard will go here once the UI is finalized.*

## CI/CD Integration
PipelineProbe can automatically fail your CI pipeline if too many critical issues are detected. See the [CI Integration Guide](docs/ci-integration.md) for details.

## Features
- **Airflow Audit**: Identifies DAG failure rates, missing retries, and SLA configurations.
- **dbt Audit**: Highlights non-tested models, test failure ratios, and model staleness.
- **Warehouse Audit**: Scans for large tables and identifies basic anti-patterns.
- **HTML Report generation**: Outputs a clear, actionable dashboard locally.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started.

## License
MIT License.
