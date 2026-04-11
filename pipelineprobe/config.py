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
}

VALID_SEVERITIES = {"critical", "warning", "info"}


class AirflowConfig(BaseModel):
    type: str = "airflow"
    base_url: str = "http://localhost:8080"
    username: str | None = None
    password: str | None = None
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


class ReportConfig(BaseModel):
    output_dir: str = "./reports"
    format: str = "html"
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
