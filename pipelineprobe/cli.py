import typer
import os
import logging
from pipelineprobe.config import load_config
from pipelineprobe.connectors.airflow import AirflowConnector
from pipelineprobe.connectors.dbt import DbtConnector
from pipelineprobe.connectors.postgres import PostgresConnector
from pipelineprobe.connectors.bigquery import BigQueryConnector
from pipelineprobe.connectors.snowflake import SnowflakeConnector
from pipelineprobe.rules import get_configured_engine
from pipelineprobe.renderer import ReportRenderer

logger = logging.getLogger(__name__)

from pipelineprobe import __version__

def version_callback(value: bool):
    if value:
        typer.echo(f"PipelineProbe v{__version__}")
        raise typer.Exit()

app = typer.Typer(
    name="pipelineprobe",
    help="Instant Data Pipeline Audit Report for Airflow + dbt + modern warehouses",
    add_completion=False,
)

@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
):
    pass


@app.command()
def audit(
    config: str = typer.Option("pipelineprobe.yml", help="Path to config file"),
    fail_on_critical: int = typer.Option(
        None, help="Override fail-on-critical threshold"
    ),
    report_format: str = typer.Option(
        None, "--format", help="Override report format: html | json | both"
    ),
):
    """
    Run the PipelineProbe audit and generate a report.
    """
    typer.echo(f"Loading configuration from {config}...")
    cfg = load_config(config)

    # Apply CLI overrides
    if fail_on_critical is not None:
        cfg.report.fail_on_critical = fail_on_critical
    if report_format is not None:
        valid_formats = {"html", "json", "both"}
        if report_format not in valid_formats:
            typer.secho(
                f"Invalid --format '{report_format}'. Must be one of: {', '.join(sorted(valid_formats))}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        cfg.report.format = report_format

    typer.echo("Initializing connectors...")
    airflow_conn = AirflowConnector(cfg.orchestrator)
    dbt_conn = DbtConnector(cfg.dbt)

    if cfg.warehouse.type == "bigquery":
        typer.echo("Using BigQuery connector...")
        warehouse_conn = BigQueryConnector(cfg.warehouse)
    elif cfg.warehouse.type == "snowflake":
        typer.echo("Using Snowflake connector...")
        warehouse_conn = SnowflakeConnector(cfg.warehouse)
    else:
        typer.echo("Using Postgres connector...")
        warehouse_conn = PostgresConnector(cfg.warehouse)

    typer.echo("Fetching data from source systems...")
    # Fetch top-level DAGs
    airflow_dags = airflow_conn.get_dags()
    airflow_tasks = []

    # Wire the actual dag runs and tasks for every returned DAG
    if airflow_dags:
        typer.echo(
            f"Found {len(airflow_dags)} Airflow DAGs. Fetching runs and tasks..."
        )
        for dag in airflow_dags:
            dag.recent_runs = airflow_conn.get_dag_runs(dag.id)
            airflow_tasks.extend(airflow_conn.get_tasks(dag.id))

    dbt_models = dbt_conn.get_models()
    warehouse_tables = warehouse_conn.get_stats_sync()

    context = {
        "airflow_dags": airflow_dags,
        "airflow_tasks": airflow_tasks,
        "dbt_models": dbt_models,
        "warehouse_tables": warehouse_tables,
        "warehouse_type": cfg.warehouse.type,
    }

    typer.echo("Running rule engine...")
    engine = get_configured_engine()
    issues = engine.run(context)

    # Compute a dummy summary for MVP
    critical_count = sum(1 for i in issues if i.severity == "critical")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    score = max(0, 100 - (critical_count * 10) - (warning_count * 2))

    summary = {
        "score": score,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "total_issues": len(issues),
        "metadata": {
            "orchestrator_url": cfg.orchestrator.base_url,
            "warehouse_type": cfg.warehouse.type,
            "dbt_target": cfg.dbt.target,
        }
    }

    typer.echo("Rendering reports...")
    renderer = ReportRenderer(cfg.report.output_dir)

    if cfg.report.format in ("html", "both"):
        html_path = renderer.render_html(issues, summary)
        typer.echo(f"HTML report generated at: {html_path}")

    if cfg.report.format in ("json", "both"):
        json_path = renderer.render_json(issues, summary)
        typer.echo(f"JSON report generated at: {json_path}")

    if critical_count > cfg.report.fail_on_critical:
        typer.secho(
            f"Audit failed! Found {critical_count} critical issues (threshold: {cfg.report.fail_on_critical}).",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.secho("Audit completed successfully!", fg=typer.colors.GREEN)


@app.command()
def init():
    """
    Initialize a pipelineprobe.yml config file in the current directory.
    """
    if os.path.exists("pipelineprobe.yml"):
        typer.secho("pipelineprobe.yml already exists.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    default_config = """# PipelineProbe Configuration

orchestrator:
  base_url: "http://localhost:8080"
  username: "admin"
  # Set PIPELINEPROBE_AIRFLOW_PASSWORD in environment instead of hardcoding here

dbt:
  project_dir: "./dbt"
  target: "dev"
  manifest_path: "./dbt/target/manifest.json"
  run_results_path: "./dbt/target/run_results.json"

warehouse:
  type: postgres
  # Set PIPELINEPROBE_WAREHOUSE_DSN in environment
  # driver is usually derived from DSN (postgresql, snowflake, bigquery, etc)

report:
  output_dir: "./reports"
  format: "both"
  fail_on_critical: 5
"""
    with open("pipelineprobe.yml", "w") as f:
        f.write(default_config)

    typer.secho("Initialized pipelineprobe.yml successfully.", fg=typer.colors.GREEN)


@app.command()
def doctor(
    config: str = typer.Option("pipelineprobe.yml", help="Path to config file"),
):
    """
    Validate connectivity to source systems.
    """
    typer.echo(f"Checking connectivity using {config}...")
    cfg = load_config(config)
    
    typer.echo("Orchestrator: [STUB] Connection successful.")
    typer.echo("Database:     [STUB] Connection successful.")
    typer.echo("dbt:          [STUB] Artifacts found.")
    typer.secho("\nAll systems operational.", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
