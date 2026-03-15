from datetime import datetime, timedelta
from pipelineprobe.rules.airflow_rules import check_missing_retries, check_missing_slas, check_stale_dags, check_high_failure_rate
from pipelineprobe.rules.postgres_rules import check_large_tables, check_missing_timestamps
from pipelineprobe.rules.dbt_rules import check_failing_models, check_missing_tests
from pipelineprobe.models import Dag, DagRun

def test_check_missing_retries(mock_airflow_tasks):
    context = {"airflow_tasks": mock_airflow_tasks}
    issues = check_missing_retries(context)
    
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "warning"
    assert "task_no_retries" in issue.affected_resources

def test_check_missing_slas(mock_airflow_tasks):
    context = {"airflow_tasks": mock_airflow_tasks}
    issues = check_missing_slas(context)
    
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "info"
    assert "task_no_retries" in issue.affected_resources

def test_check_stale_dags():
    dags = [
        Dag(id="stale_dag", is_active=True, owner="test", recent_runs=[
            DagRun(state="success", start_time=datetime.now() - timedelta(days=10), end_time=datetime.now() - timedelta(days=10))
        ]),
        Dag(id="fresh_dag", is_active=True, owner="test", recent_runs=[
            DagRun(state="success", start_time=datetime.now() - timedelta(days=1), end_time=datetime.now() - timedelta(days=1))
        ]),
        Dag(id="no_runs_dag", is_active=True, owner="test", recent_runs=[])
    ]
    issues = check_stale_dags({"airflow_dags": dags})
    assert len(issues) == 2
    affected = [res for issue in issues for res in issue.affected_resources]
    assert "stale_dag" in affected
    assert "no_runs_dag" in affected

def test_check_high_failure_rate():
    dags = [
        # 5 runs, 3 failed = 60% failure rate (>20%)
        Dag(id="failing_dag", is_active=True, owner="test", recent_runs=[
            DagRun(state="failed", start_time=datetime.now(), end_time=datetime.now()),
            DagRun(state="failed", start_time=datetime.now(), end_time=datetime.now()),
            DagRun(state="failed", start_time=datetime.now(), end_time=datetime.now()),
            DagRun(state="success", start_time=datetime.now(), end_time=datetime.now()),
            DagRun(state="success", start_time=datetime.now(), end_time=datetime.now())
        ]),
        # 5 runs, 0 failed
        Dag(id="ok_dag", is_active=True, owner="test", recent_runs=[
            DagRun(state="success", start_time=datetime.now(), end_time=datetime.now()) for _ in range(5)
        ])
    ]
    issues = check_high_failure_rate({"airflow_dags": dags})
    assert len(issues) == 1
    assert "failing_dag" in issues[0].affected_resources

def test_check_large_tables(mock_postgres_tables):
    context = {"postgres_tables": mock_postgres_tables}
    issues = check_large_tables(context)
    
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "warning"
    assert "huge_table" in issue.affected_resources

def test_check_missing_timestamps():
    tables = [
        {"tablename": "huge_no_ts", "row_count": 5_000_000, "has_timestamps": False},
        {"tablename": "huge_with_ts", "row_count": 5_000_000, "has_timestamps": True},
        {"tablename": "small_no_ts", "row_count": 100, "has_timestamps": False}
    ]
    issues = check_missing_timestamps({"postgres_tables": tables})
    assert len(issues) == 1
    assert "huge_no_ts" in issues[0].affected_resources

def test_check_missing_tests(mock_dbt_models):
    issues = check_missing_tests({"dbt_models": mock_dbt_models})
    assert len(issues) == 1
    assert "model_with_no_tests" in issues[0].affected_resources

def test_check_failing_models():
    from pipelineprobe.models import DbtModel
    models = [
        DbtModel(name="failing_model", tests_count=1, last_run_status="error", tags=[]),
        DbtModel(name="test_fail", tests_count=1, last_run_status="fail", tags=[]),
        DbtModel(name="ok_model", tests_count=1, last_run_status="success", tags=[])
    ]
    issues = check_failing_models({"dbt_models": models})
    assert len(issues) == 2
    affected = [res for issue in issues for res in issue.affected_resources]
    assert "failing_model" in affected
    assert "test_fail" in affected

def test_rule_engine_error():
    from pipelineprobe.rules.engine import RuleEngine
    engine = RuleEngine()
    
    def buggy_rule(context):
        raise Exception("Rule Bug")
    
    engine.register_rule(buggy_rule)
    # Should handle exception and continue/return current issues
    issues = engine.run({})
    assert issues == []
