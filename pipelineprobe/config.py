import yaml
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class AirflowConfig(BaseModel):
    type: str = "airflow"
    base_url: str = "http://localhost:8080"
    username: str = "admin"
    password: str = "admin"
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

class PipelineProbeConfig(BaseSettings):
    orchestrator: AirflowConfig = AirflowConfig()
    dbt: DbtConfig = DbtConfig()
    warehouse: WarehouseConfig = WarehouseConfig()
    report: ReportConfig = ReportConfig()

def load_config(config_path: str) -> PipelineProbeConfig:
    """Load config from YAML if it exists, otherwise return defaults."""
    path = Path(config_path)
    if path.exists():
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
            # BaseSettings automatically merges env vars
            return PipelineProbeConfig(**data)
    return PipelineProbeConfig()
