import typer
from pipelineprobe.config import load_config
from pipelineprobe.connectors.airflow import AirflowConnector
from pipelineprobe.connectors.dbt import DbtConnector
from pipelineprobe.connectors.postgres import PostgresConnector
from pipelineprobe.rules import get_configured_engine
from pipelineprobe.renderer import ReportRenderer

app = typer.Typer(
    name="pipelineprobe",
    help="Instant Data Pipeline Audit Report for Airflow + dbt + modern warehouses",
    add_completion=False,
)

@app.command()
def audit(config: str = typer.Option("pipelineprobe.yml", help="Path to config file")):
    """
    Run the PipelineProbe audit and generate a report.
    """
    typer.echo(f"Loading configuration from {config}...")
    cfg = load_config(config)

    typer.echo("Initializing connectors...")
    airflow_conn = AirflowConnector(cfg.orchestrator)
    dbt_conn = DbtConnector(cfg.dbt)
    pg_conn = PostgresConnector(cfg.warehouse)

    typer.echo("Fetching data from source systems...")
    # These might fail depending on user's exact setup during MVP testing,
    # so we gently collect what we can.
    airflow_dags = airflow_conn.get_dags()
    airflow_tasks = []
    if airflow_dags:
        # Just grab tasks for first DAG as a stub
        airflow_tasks = airflow_conn.get_tasks(airflow_dags[0].id)
        
    dbt_models = dbt_conn.get_models()
    postgres_tables = pg_conn.get_stats_sync()

    context = {
        "airflow_dags": airflow_dags,
        "airflow_tasks": airflow_tasks,
        "dbt_models": dbt_models,
        "postgres_tables": postgres_tables,
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
        "total_issues": len(issues)
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
        typer.secho(f"Audit failed! Found {critical_count} critical issues (threshold: {cfg.report.fail_on_critical}).", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("Audit completed successfully!", fg=typer.colors.GREEN)

@app.command()
def init():
    """
    Initialize a pipelineprobe.yml config file in the current directory.
    """
    typer.echo("Initialized pipelineprobe.yml (Not implemented yet).")

if __name__ == "__main__":
    app()
