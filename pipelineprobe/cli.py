import asyncio
import json
import logging
import os
from pathlib import Path

import httpx
import typer

from pipelineprobe import __version__
from pipelineprobe.config import load_config, SUPPORTED_ORCHESTRATORS
from pipelineprobe.connectors.airflow import AirflowConnector
from pipelineprobe.connectors.prefect import PrefectConnector
from pipelineprobe.connectors.dagster import DagsterConnector
from pipelineprobe.connectors.dbt import DbtConnector
from pipelineprobe.connectors.postgres import PostgresConnector
from pipelineprobe.connectors.bigquery import BigQueryConnector
from pipelineprobe.connectors.snowflake import SnowflakeConnector
from pipelineprobe.rules import get_configured_engine
from pipelineprobe.renderer import ReportRenderer

logger = logging.getLogger(__name__)


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

    # ------------------------------------------------------------------
    # Orchestrator connector — Airflow (default), Prefect, or Dagster
    # ------------------------------------------------------------------
    orch_type = cfg.orchestrator.type.lower()
    if orch_type not in SUPPORTED_ORCHESTRATORS:
        typer.secho(
            f"Unknown orchestrator type '{orch_type}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_ORCHESTRATORS))}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    orchestrator_dags: list = []
    orchestrator_tasks: list = []

    if orch_type == "prefect":
        typer.echo(f"Using Prefect connector ({cfg.orchestrator.base_url})...")
        prefect_conn = PrefectConnector(cfg.orchestrator)
        orchestrator_dags = prefect_conn.get_dags()
        typer.echo(f"  Found {len(orchestrator_dags)} Prefect flows.")

    elif orch_type == "dagster":
        typer.echo(f"Using Dagster connector ({cfg.orchestrator.base_url})...")
        dagster_conn = DagsterConnector(cfg.orchestrator)
        orchestrator_dags = dagster_conn.get_dags()
        typer.echo(f"  Found {len(orchestrator_dags)} Dagster jobs.")

    else:  # airflow (default)
        airflow_conn = AirflowConnector(cfg.orchestrator)
        orchestrator_dags = airflow_conn.get_dags()
        if orchestrator_dags:
            typer.echo(
                f"Found {len(orchestrator_dags)} Airflow DAGs. "
                f"Fetching runs and tasks concurrently "
                f"(concurrency={cfg.rules.fetch_concurrency})..."
            )
            orchestrator_dags, orchestrator_tasks = asyncio.run(
                airflow_conn.fetch_dag_details(
                    orchestrator_dags, concurrency=cfg.rules.fetch_concurrency
                )
            )

    # ------------------------------------------------------------------
    # Warehouse connector
    # ------------------------------------------------------------------
    dbt_conn = DbtConnector(cfg.dbt)

    if cfg.warehouse.type == "bigquery":
        typer.echo("Using BigQuery connector...")
        warehouse_conn: BigQueryConnector | SnowflakeConnector | PostgresConnector = (
            BigQueryConnector(cfg.warehouse)
        )
    elif cfg.warehouse.type == "snowflake":
        typer.echo("Using Snowflake connector...")
        warehouse_conn = SnowflakeConnector(cfg.warehouse)
    else:
        typer.echo("Using Postgres connector...")
        warehouse_conn = PostgresConnector(cfg.warehouse)

    typer.echo("Fetching data from source systems...")
    dbt_models = dbt_conn.get_models()
    warehouse_tables = warehouse_conn.get_stats_sync()

    # ------------------------------------------------------------------
    # Optional cost insights (v0.3.0)
    # ------------------------------------------------------------------
    bq_cost_insights: list = []
    sf_cost_insights: list = []

    if cfg.report.include_cost_section:
        typer.echo("Fetching cost insights...")
        if cfg.warehouse.type == "bigquery" and isinstance(warehouse_conn, BigQueryConnector):
            bq_cost_insights = warehouse_conn.get_cost_insights_sync()
            typer.echo(f"  BigQuery: {len(bq_cost_insights)} tables with cost data.")
        elif cfg.warehouse.type == "snowflake" and isinstance(warehouse_conn, SnowflakeConnector):
            sf_cost_insights = warehouse_conn.get_cost_insights_sync()
            typer.echo(f"  Snowflake: {len(sf_cost_insights)} warehouses with credit data.")

    context = {
        # The existing Airflow rules operate on "airflow_dags" / "airflow_tasks".
        # Prefect and Dagster connectors populate the same keys via the shared
        # Dag / Task models so all orchestrator rules work without modification.
        "airflow_dags": orchestrator_dags,
        "airflow_tasks": orchestrator_tasks,
        "orchestrator_type": orch_type,
        "dbt_models": dbt_models,
        "warehouse_tables": warehouse_tables,
        "warehouse_type": cfg.warehouse.type,
        # Cost insights — empty lists when include_cost_section=false
        "bq_cost_insights": bq_cost_insights,
        "sf_cost_insights": sf_cost_insights,
        # Rule-level configuration injected into context so rules stay stateless
        "rule_severity_overrides": cfg.rules.severity_overrides,
        "stale_threshold_days": cfg.rules.stale_threshold_days,
    }

    typer.echo("Running rule engine...")
    engine = get_configured_engine()
    issues = engine.run(context)

    # -----------------------------------------------------------------------
    # Health score — normalized by DAG count so that five criticals on a
    # 500-DAG shop is a very different signal than five on a 10-DAG shop.
    #
    # Formula:
    #   critical_density = critical_count / dag_count   (criticals per DAG)
    #   warning_density  = warning_count  / dag_count   (warnings per DAG)
    #
    #   critical_penalty = min(90, critical_density * 200)
    #     → 45 % critical density → 90-pt penalty (score ≤ 10 before warnings)
    #     → 1  % critical density →  2-pt penalty (barely dents the score)
    #
    #   warning_penalty  = min(20, warning_density * 40)
    #     → 50 % warning  density → 20-pt penalty
    #     → 5  % warning  density →  2-pt penalty
    #
    #   score = max(0, round(100 - critical_penalty - warning_penalty))
    # -----------------------------------------------------------------------
    dag_count = max(1, len(orchestrator_dags))
    critical_count = sum(1 for i in issues if i.severity == "critical")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    critical_density = critical_count / dag_count
    warning_density = warning_count / dag_count

    critical_penalty = min(90.0, critical_density * 200.0)
    warning_penalty = min(20.0, warning_density * 40.0)
    score = max(0, round(100.0 - critical_penalty - warning_penalty))

    summary = {
        "score": score,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "total_issues": len(issues),
        "dag_count": dag_count,
        "score_formula": (
            f"score = 100 - min(90, {critical_density:.3f} criticals/DAG × 200) "
            f"- min(20, {warning_density:.3f} warnings/DAG × 40)"
        ),
        "metadata": {
            "orchestrator_url": cfg.orchestrator.base_url,
            "orchestrator_type": orch_type,
            "warehouse_type": cfg.warehouse.type,
            "dbt_target": cfg.dbt.target,
            "cost_insights_enabled": cfg.report.include_cost_section,
        },
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
  # Supported types: airflow | prefect | dagster
  type: airflow
  base_url: "http://localhost:8080"
  username: "admin"
  # Set PIPELINEPROBE_AIRFLOW_PASSWORD in environment instead of hardcoding here

  # Prefect / Dagster Cloud: set api_key to your personal access token.
  # api_key: ""

dbt:
  project_dir: "./dbt"
  target: "dev"
  manifest_path: "./dbt/target/manifest.json"
  run_results_path: "./dbt/target/run_results.json"

warehouse:
  type: postgres
  # Set PIPELINEPROBE_WAREHOUSE_DSN in environment
  # driver is usually derived from DSN (postgresql, snowflake, bigquery, etc)

  # BigQuery: override default query region (default: region-us)
  # bq_region: "region-eu"

report:
  output_dir: "./reports"
  format: "both"
  fail_on_critical: 5

  # Set to true to run cost-insight queries (BigQuery bytes billed,
  # Snowflake credit consumption) and include findings in the report.
  # Requires JOBS_BY_PROJECT access on BigQuery or ACCOUNTADMIN on Snowflake.
  include_cost_section: false

rules:
  # How many days without a successful run before a pipeline is flagged as stale.
  stale_threshold_days: 7

  # Maximum concurrent Airflow API calls during audit (runs + tasks per DAG).
  # Not used for Prefect / Dagster connectors.
  fetch_concurrency: 10

  # Per-rule severity overrides.  Uncomment and adjust to match your team's SLAs.
  # Valid severities: critical | warning | info
  # severity_overrides:
  #   missing_sla: critical          # fintech / real-time teams often require SLAs
  #   missing_retries: warning       # default
  #   stale_dags: warning            # default
  #   high_failure_rate: critical    # default
  #   expensive_bq_tables: warning   # default
  #   snowflake_credit_spenders: warning  # default
"""
    with open("pipelineprobe.yml", "w") as f:
        f.write(default_config)

    typer.secho("Initialized pipelineprobe.yml successfully.", fg=typer.colors.GREEN)


@app.command()
def doctor(
    config: str = typer.Option("pipelineprobe.yml", help="Path to config file"),
):
    """
    Validate connectivity to Airflow, dbt artifacts, and the configured warehouse.
    """
    typer.echo(f"Checking connectivity using {config}...\n")
    cfg = load_config(config)
    all_ok = True

    # ------------------------------------------------------------------
    # 1. Orchestrator connectivity probe
    # ------------------------------------------------------------------
    orch_type = cfg.orchestrator.type.lower()
    typer.echo(f"[Orchestrator — {orch_type}]")

    headers: dict = {}
    if cfg.orchestrator.api_key:
        if orch_type == "dagster":
            headers["Dagster-Cloud-Api-Token"] = cfg.orchestrator.api_key
        else:
            headers["Authorization"] = f"Bearer {cfg.orchestrator.api_key}"

    auth = (
        (cfg.orchestrator.username, cfg.orchestrator.password)
        if cfg.orchestrator.username and cfg.orchestrator.password
        else None
    )

    try:
        with httpx.Client(
            base_url=cfg.orchestrator.base_url,
            auth=auth,
            headers=headers,
            verify=cfg.orchestrator.verify_ssl,
            timeout=10.0,
        ) as client:
            if orch_type == "airflow":
                resp = client.get("/api/v1/health")
                resp.raise_for_status()
                health = resp.json()
                meta_status = health.get("metadatabase", {}).get("status", "unknown")
                sched_status = health.get("scheduler", {}).get("status", "unknown")
                typer.secho(
                    f"  Connection:   OK  ({cfg.orchestrator.base_url})",
                    fg=typer.colors.GREEN,
                )
                _print_status_line("  Metadatabase:", meta_status)
                _print_status_line("  Scheduler:   ", sched_status)

            elif orch_type == "prefect":
                # Prefect health endpoint available in both Server and Cloud
                resp = client.get("/api/health")
                resp.raise_for_status()
                typer.secho(
                    f"  Connection:   OK  ({cfg.orchestrator.base_url})",
                    fg=typer.colors.GREEN,
                )

            elif orch_type == "dagster":
                # Dagster GraphQL introspection confirms the API is reachable
                resp = client.post(
                    "/graphql",
                    json={"query": "{ __typename }"},
                )
                resp.raise_for_status()
                typer.secho(
                    f"  Connection:   OK  ({cfg.orchestrator.base_url})",
                    fg=typer.colors.GREEN,
                )

            else:
                typer.secho(
                    f"  Unknown orchestrator type '{orch_type}' — skipping probe.",
                    fg=typer.colors.YELLOW,
                )

    except httpx.HTTPStatusError as exc:
        typer.secho(
            f"  Connection:   FAIL  (HTTP {exc.response.status_code}: {exc.response.text[:120]})",
            fg=typer.colors.RED,
        )
        all_ok = False
    except Exception as exc:
        typer.secho(f"  Connection:   FAIL  ({exc})", fg=typer.colors.RED)
        all_ok = False

    # ------------------------------------------------------------------
    # 2. dbt artifacts — check manifest.json (required) and run_results.json
    # ------------------------------------------------------------------
    typer.echo("\n[dbt]")
    manifest = Path(cfg.dbt.manifest_path)
    run_results = Path(cfg.dbt.run_results_path)

    if manifest.exists():
        typer.secho(f"  manifest.json:     Found   ({manifest})", fg=typer.colors.GREEN)
    else:
        typer.secho(f"  manifest.json:     MISSING ({manifest})", fg=typer.colors.RED)
        all_ok = False

    if run_results.exists():
        typer.secho(
            f"  run_results.json:  Found   ({run_results})", fg=typer.colors.GREEN
        )
    else:
        # run_results is optional — warn but don't fail
        typer.secho(
            f"  run_results.json:  MISSING ({run_results})  [optional — some rules may be skipped]",
            fg=typer.colors.YELLOW,
        )

    # ------------------------------------------------------------------
    # 3. Warehouse — light connectivity probe per driver
    # ------------------------------------------------------------------
    typer.echo(f"\n[Warehouse — {cfg.warehouse.type}]")
    try:
        if cfg.warehouse.type == "postgres":
            import psycopg2

            conn = psycopg2.connect(cfg.warehouse.dsn, connect_timeout=10)
            conn.close()
            dsn_safe = cfg.warehouse.dsn.split("@")[-1] if "@" in cfg.warehouse.dsn else cfg.warehouse.dsn
            typer.secho(
                f"  Postgres:  OK  (@{dsn_safe})", fg=typer.colors.GREEN
            )

        elif cfg.warehouse.type == "bigquery":
            from google.cloud import bigquery

            client = bigquery.Client(project=cfg.warehouse.project_id)
            # list_datasets is the lightest possible probe
            next(iter(client.list_datasets(max_results=1)), None)
            typer.secho(
                f"  BigQuery:  OK  (project={cfg.warehouse.project_id})",
                fg=typer.colors.GREEN,
            )

        elif cfg.warehouse.type == "snowflake":
            import snowflake.connector

            conn = snowflake.connector.connect(
                account=cfg.warehouse.account,
                user=cfg.warehouse.username,
                password=cfg.warehouse.password,
                login_timeout=10,
            )
            conn.close()
            typer.secho(
                f"  Snowflake: OK  (account={cfg.warehouse.account})",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                f"  Unknown warehouse type '{cfg.warehouse.type}' — skipping probe.",
                fg=typer.colors.YELLOW,
            )

    except Exception as exc:
        typer.secho(
            f"  {cfg.warehouse.type}: FAIL  ({exc})", fg=typer.colors.RED
        )
        all_ok = False

    # ------------------------------------------------------------------
    # 4. Cost-insight probe (only when include_cost_section=true)
    # ------------------------------------------------------------------
    if cfg.report.include_cost_section:
        typer.echo("\n[Cost Insights]")
        try:
            if cfg.warehouse.type == "bigquery":
                from google.cloud import bigquery as bq_lib

                bq_client = bq_lib.Client(project=cfg.warehouse.project_id)
                project = bq_client.project
                region = cfg.warehouse.bq_region or "region-us"
                probe_q = (
                    f"SELECT COUNT(1) AS n "
                    f"FROM `{project}`.`{region}`.INFORMATION_SCHEMA.JOBS_BY_PROJECT "
                    f"LIMIT 1"
                )
                bq_client.query(probe_q).result()
                typer.secho(
                    "  BigQuery JOBS_BY_PROJECT: accessible", fg=typer.colors.GREEN
                )
            elif cfg.warehouse.type == "snowflake":
                import snowflake.connector as sf

                conn = sf.connect(
                    account=cfg.warehouse.account,
                    user=cfg.warehouse.username,
                    password=cfg.warehouse.password,
                    login_timeout=10,
                )
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(1) FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY LIMIT 1"
                )
                cur.close()
                conn.close()
                typer.secho(
                    "  Snowflake WAREHOUSE_METERING_HISTORY: accessible",
                    fg=typer.colors.GREEN,
                )
            else:
                typer.secho(
                    f"  Cost insights not supported for warehouse type '{cfg.warehouse.type}'.",
                    fg=typer.colors.YELLOW,
                )
        except Exception as exc:
            typer.secho(f"  Cost insights: FAIL  ({exc})", fg=typer.colors.RED)
            all_ok = False

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    typer.echo()
    if all_ok:
        typer.secho("All systems operational.", fg=typer.colors.GREEN)
    else:
        typer.secho(
            "One or more checks failed — review the output above before running audit.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


def _print_status_line(label: str, status: str) -> None:
    """Print a labelled status value coloured green/red based on 'healthy'."""
    color = typer.colors.GREEN if status == "healthy" else typer.colors.YELLOW
    typer.secho(f"{label} {status}", fg=color)


@app.command()
def diff(
    report_a: str = typer.Argument(..., help="Path to the baseline JSON report"),
    report_b: str = typer.Argument(..., help="Path to the current JSON report"),
):
    """
    Compare two audit JSON reports and show regressions and improvements.

    Exit code 1 if any regressions are found, 0 otherwise.
    """
    path_a, path_b = Path(report_a), Path(report_b)

    for p in (path_a, path_b):
        if not p.exists():
            typer.secho(f"Report not found: {p}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    with open(path_a) as f:
        data_a = json.load(f)
    with open(path_b) as f:
        data_b = json.load(f)

    score_a = data_a.get("summary", {}).get("score", 0)
    score_b = data_b.get("summary", {}).get("score", 0)
    delta = score_b - score_a

    # Fingerprint issues by (severity, summary) to detect changes.
    # This is intentionally coarse — rule text changes will show as new issues,
    # which is the desired behaviour during rule updates.
    def _fp(issue: dict) -> str:
        return f"{issue['severity']}|{issue['summary']}"

    fp_a = {_fp(i): i for i in data_a.get("issues", [])}
    fp_b = {_fp(i): i for i in data_b.get("issues", [])}

    regressions = {k: v for k, v in fp_b.items() if k not in fp_a}
    improvements = {k: v for k, v in fp_a.items() if k not in fp_b}
    unchanged_count = sum(1 for k in fp_b if k in fp_a)

    # ---- Header ----
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    delta_color = typer.colors.GREEN if delta >= 0 else typer.colors.RED
    typer.echo(f"Baseline : {report_a}  (score {score_a})")
    typer.echo(f"Current  : {report_b}  (score {score_b})")
    typer.secho(f"Score delta: {delta_str}", fg=delta_color, bold=True)

    # ---- Regressions ----
    if regressions:
        typer.secho(
            f"\n{len(regressions)} Regression(s) — new issues in current report:",
            fg=typer.colors.RED,
            bold=True,
        )
        _SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
        for issue in sorted(
            regressions.values(), key=lambda x: _SEVERITY_ORDER.get(x["severity"], 9)
        ):
            sev_color = (
                typer.colors.RED
                if issue["severity"] == "critical"
                else typer.colors.YELLOW
            )
            typer.secho(
                f"  [{issue['severity'].upper()}] {issue['summary']}", fg=sev_color
            )
            if issue.get("recommendation"):
                typer.echo(f"           → {issue['recommendation']}")

    # ---- Improvements ----
    if improvements:
        typer.secho(
            f"\n{len(improvements)} Improvement(s) — issues resolved since baseline:",
            fg=typer.colors.GREEN,
            bold=True,
        )
        for issue in improvements.values():
            typer.secho(
                f"  [{issue['severity'].upper()}] {issue['summary']}", fg=typer.colors.GREEN
            )

    if not regressions and not improvements:
        typer.echo("\nNo changes detected between reports.")

    # ---- Footer ----
    typer.echo(
        f"\nSummary: {unchanged_count} unchanged, "
        f"{len(regressions)} regression(s), "
        f"{len(improvements)} improvement(s)."
    )

    if regressions:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
