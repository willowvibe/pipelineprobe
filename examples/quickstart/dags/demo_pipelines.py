"""Deterministic demo DAGs for the PipelineProbe quickstart.

Seeded problems (so the audit has something to find):

* ``daily_sales_pipeline`` and ``nightly_customer_sync`` have one task each
  with ``retries=0``, no SLA, and no email alerting.
* ``nightly_customer_sync`` fails on the runs named ``seed_3`` and ``seed_6``,
  giving it a 2/6 (33%) failure rate once run-audit.sh seeds its history.

The six ``healthy_pipeline_*`` DAGs have retries and an SLA so the eight-DAG
population keeps the health-score normalization realistic.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

FAILING_SEEDS = {"seed_3", "seed_6"}

COMMON_ARGS = {
    "start_date": datetime(2024, 1, 1),
    "schedule": None,
    "catchup": False,
    "is_paused_upon_creation": False,
    "tags": ["quickstart"],
}


def _sync_customers(**context) -> None:
    """Succeed normally, but fail for the two runs that seed the demo."""
    run_id = context.get("run_id", "")
    print(f"nightly_customer_sync executing {run_id}")
    if run_id in FAILING_SEEDS:
        raise RuntimeError(f"Simulated upstream failure for run {run_id}")


with DAG(dag_id="daily_sales_pipeline", **COMMON_ARGS) as daily_sales_pipeline:
    EmptyOperator(task_id="load_daily_sales", retries=0)

with DAG(dag_id="nightly_customer_sync", **COMMON_ARGS) as nightly_customer_sync:
    PythonOperator(
        task_id="sync_customers",
        python_callable=_sync_customers,
        retries=0,
    )

HEALTHY_TASK_ARGS = {
    "retries": 2,
    "sla": timedelta(hours=1),
}

for index in range(1, 7):
    dag_id = f"healthy_pipeline_{index}"
    with DAG(dag_id=dag_id, **COMMON_ARGS) as dag:
        EmptyOperator(task_id="run", **HEALTHY_TASK_ARGS)
    # Each DAG must be a distinct module-level global, otherwise the DagBag
    # keeps only the last DAG created by the loop.
    globals()[dag_id] = dag
