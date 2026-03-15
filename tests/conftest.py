import pytest
from datetime import datetime, timedelta
from pipelineprobe.models import Dag, DagRun, Task, DbtModel

@pytest.fixture
def mock_airflow_dags():
    return [
        Dag(
            id="test_dag_1",
            is_active=True,
            recent_runs=[
                DagRun(state="failed", start_time=datetime.now() - timedelta(days=1), end_time=datetime.now()),
                DagRun(state="failed", start_time=datetime.now() - timedelta(days=2), end_time=datetime.now() - timedelta(days=1)),
            ],
            owner="data_engineering"
        ),
        Dag(
            id="test_dag_2",
            is_active=True,
            recent_runs=[
                DagRun(state="success", start_time=datetime.now() - timedelta(hours=2), end_time=datetime.now()),
            ],
            owner="analytics"
        )
    ]

@pytest.fixture
def mock_airflow_tasks():
    return [
        Task(dag_id="test_dag_1", task_id="task_no_retries", retries=0, sla=None, has_alerts=False),
        Task(dag_id="test_dag_1", task_id="task_with_retries", retries=3, sla=timedelta(hours=1), has_alerts=True),
    ]

@pytest.fixture
def mock_dbt_models():
    return [
        DbtModel(name="model_with_no_tests", tests_count=0, last_run_status="success", tags=[]),
        DbtModel(name="model_with_tests", tests_count=5, last_run_status="success", tags=["daily"]),
    ]

@pytest.fixture
def mock_postgres_tables():
    return [
        {"schemaname": "public", "tablename": "huge_table", "row_count": 50_000_000},
        {"schemaname": "public", "tablename": "small_table", "row_count": 100},
    ]
