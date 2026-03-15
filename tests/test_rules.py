from pipelineprobe.rules.airflow_rules import check_missing_retries, check_missing_slas
from pipelineprobe.rules.postgres_rules import check_large_tables

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

def test_check_large_tables(mock_postgres_tables):
    context = {"postgres_tables": mock_postgres_tables}
    issues = check_large_tables(context)
    
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "warning"
    assert "huge_table" in issue.affected_resources
