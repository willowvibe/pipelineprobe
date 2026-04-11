import yaml
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings

# Valid rule names that can have their severity overridden via YAML config.
OVERRIDABLE_RULES = {
    "missing_sla",
    "missing_retries",
    "high_failure_rate",
    "stale_dags",
    "missing_dbt_tests",
    "failing_dbt_models",
    # cost rules (v0.3.0)
    "expensive_bq_tables",
    "snowflake_credit_spenders",
}

VALID_SEVERITIES = {"critical", "warning", "info"}

# Orchestrator types supported by the CLI router.
SUPPORTED_ORCHESTRATORS = {"airflow", "prefect", "dagster"}


class AirflowConfig(BaseModel):
    """Generic orchestrator configuration.

    ``type`` selects the connector:

    * ``airflow``  — Apache Airflow REST API (≥ 2.0)
    * ``prefect``  — Prefect 2 / 3 (Server or Cloud)
    * ``dagster``  — Dagster (open-source or Dagster Cloud)
    """

    type: str = "airflow"
    base_url: str = "http://localhost:8080"
    username: str | None = None
    password: str | None = None
    # API key / bearer token used by Prefect Cloud and Dagster Cloud.
    # For Prefect set to your personal access token.
    # For Dagster Cloud set to your user token.
    api_key: str | None = None
    verify_ssl: bool = False
    lookback_days: int = 14


class DbtConfig(BaseModel):
    project_dir: str = "./analytics"
    target: str = "prod"
    manifest_path: str = "./analytics/target/manifest.json"
    run_results_path: str = "./analytics/target/run_results.json"


class WarehouseConfig(BaseModel):
    type: str = "postgres"
    dsn: str = "postgresql://user:pass@localhost:5432/analytics"
    account: str | None = None
    project_id: str | None = None
    username: str | None = None
    password: str | None = None
    # BigQuery: override the default region for INFORMATION_SCHEMA queries.
    # Defaults to "region-us".  Set to e.g. "region-eu" for EU multi-region.
    bq_region: str | None = None


class ReportConfig(BaseModel):
    output_dir: str = "./reports"
    format: str = "html"
    # Set to true to run cost-insight queries (BigQuery bytes billed,
    # Snowflake credits) and include results in the audit report.
    # Requires appropriate IAM permissions (BigQuery: JOBS_BY_PROJECT view;
    # Snowflake: ACCOUNTADMIN or ACCOUNT_USAGE privilege).
    include_cost_section: bool = False
    fail_on_critical: int = 5


class RulesConfig(BaseModel):
    # Per-rule severity overrides.  Keys must be one of OVERRIDABLE_RULES;
    # values must be one of VALID_SEVERITIES.
    # Example YAML:
    #   rules:
    #     severity_overrides:
    #       missing_sla: critical   # fintech teams often treat this as critical
    #       stale_dags: warning
    severity_overrides: dict[str, str] = {}

    # How many days without a successful run before a DAG is considered stale.
    stale_threshold_days: int = 7

    # Concurrency limit for async Airflow API calls during audit.
    fetch_concurrency: int = 10


class PipelineProbeConfig(BaseSettings):
    orchestrator: AirflowConfig = AirflowConfig()
    dbt: DbtConfig = DbtConfig()
    warehouse: WarehouseConfig = WarehouseConfig()
    report: ReportConfig = ReportConfig()
    rules: RulesConfig = RulesConfig()


def load_config(config_path: str) -> PipelineProbeConfig:
    """Load config from YAML if it exists, otherwise return defaults."""
    path = Path(config_path)
    if path.exists():
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
            # BaseSettings automatically merges env vars
            return PipelineProbeConfig(**data)
    return PipelineProbeConfig()
