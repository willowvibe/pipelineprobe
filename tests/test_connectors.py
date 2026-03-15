import json
from unittest.mock import patch, MagicMock

from pipelineprobe.config import WarehouseConfig, DbtConfig, AirflowConfig
from pipelineprobe.connectors.postgres import PostgresConnector
from pipelineprobe.connectors.dbt import DbtConnector
from pipelineprobe.connectors.snowflake import SnowflakeConnector
from pipelineprobe.connectors.bigquery import BigQueryConnector
from pipelineprobe.connectors.airflow import AirflowConnector


@patch("pipelineprobe.connectors.postgres.psycopg2.connect")
def test_postgres_connector(mock_connect):
    config = WarehouseConfig(type="postgres", dsn="postgresql://fake")
    connector = PostgresConnector(config)

    # Mock context manager cursor
    mock_cursor = mock_connect.return_value.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [
        {
            "schemaname": "public",
            "tablename": "users",
            "row_count": 100,
            "has_timestamps": True,
        }
    ]

    stats_sync = connector.get_stats_sync()
    assert len(stats_sync) == 1
    assert stats_sync[0]["has_timestamps"] is True


@patch("pipelineprobe.connectors.postgres.psycopg2.connect")
def test_postgres_connector_error(mock_connect):
    config = WarehouseConfig(type="postgres", dsn="postgresql://fake")
    connector = PostgresConnector(config)

    mock_connect.side_effect = Exception("DB Down")
    stats = connector.get_stats_sync()
    assert stats == []


def test_snowflake_connector_missing_creds():
    # Snowflake connector should validate account, username, password
    config = WarehouseConfig(type="snowflake")
    connector = SnowflakeConnector(config)
    stats = connector.get_stats_sync()
    assert stats == []


@patch("pipelineprobe.connectors.snowflake.snowflake.connector.connect")
def test_snowflake_connector(mock_connect):
    config = WarehouseConfig(
        type="snowflake", account="acc", username="usr", password="pw"
    )
    connector = SnowflakeConnector(config)

    # Mock cursors
    mock_cursor = mock_connect.return_value.cursor.return_value
    mock_cursor.fetchall.return_value = [("PUBLIC", "USERS", 100, True)]

    stats = connector.get_stats_sync()
    assert len(stats) == 1
    assert stats[0]["tablename"] == "USERS"
    assert stats[0]["has_timestamps"] is True


@patch("pipelineprobe.connectors.snowflake.snowflake.connector.connect")
def test_snowflake_connector_error(mock_connect):
    config = WarehouseConfig(
        type="snowflake", account="acc", username="usr", password="pw"
    )
    connector = SnowflakeConnector(config)
    mock_connect.side_effect = Exception("Snowflake Error")
    stats = connector.get_stats_sync()
    assert stats == []


@patch("pipelineprobe.connectors.bigquery.bigquery.Client")
def test_bigquery_connector(mock_client_cls):
    config = WarehouseConfig(type="bigquery", project_id="test_project")
    connector = BigQueryConnector(config)

    mock_client = mock_client_cls.return_value

    mock_job = MagicMock()

    # Mock row object which behaves like a namedtuple/dict in BigQuery
    class MockRow:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    mock_job.result.return_value = [
        MockRow(
            schemaname="public", tablename="users", row_count=100, has_timestamps=True
        )
    ]
    mock_client.query.return_value = mock_job

    stats = connector.get_stats_sync()
    assert len(stats) == 1
    assert stats[0]["schemaname"] == "public"


@patch("pipelineprobe.connectors.bigquery.bigquery.Client")
def test_bigquery_connector_error(mock_client_cls):
    config = WarehouseConfig(type="bigquery", project_id="test_project")
    connector = BigQueryConnector(config)
    mock_client_cls.side_effect = Exception("BQ Error")
    stats = connector.get_stats_sync()
    assert stats == []


def test_dbt_connector_no_files(tmp_path):
    config = DbtConfig(
        project_dir=str(tmp_path),
        manifest_path="manifest.json",
        run_results_path="rr.json",
    )
    connector = DbtConnector(config)
    models = connector.get_models()
    assert models == []


def test_dbt_connector_success(tmp_path):
    manifest = {
        "nodes": {
            "model.test.users": {
                "resource_type": "model",
                "name": "users",
                "unique_id": "model.test.users",
                "tags": ["daily"],
            },
            "test.test.not_null_users_id": {
                "resource_type": "test",
                "attached_node": "model.test.users",
                "depends_on": {"nodes": ["model.test.users"]},
                "unique_id": "test.test.not_null_users_id",
            },
        }
    }
    rr = {"results": [{"unique_id": "model.test.users", "status": "success"}]}

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    rr_path = tmp_path / "rr.json"
    rr_path.write_text(json.dumps(rr))

    config = DbtConfig(
        project_dir=str(tmp_path),
        manifest_path=str(manifest_path),
        run_results_path=str(rr_path),
    )
    connector = DbtConnector(config)

    models = connector.get_models()
    assert len(models) == 1
    assert models[0].name == "users"
    assert models[0].tests_count == 1
    assert models[0].last_run_status == "success"


@patch("httpx.Client")
def test_airflow_connector(mock_httpx_client):
    config = AirflowConfig(base_url="http://fake", username="u", password="p")

    # Mock get_dags setup
    mock_response_1 = MagicMock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = {
        "dags": [{"dag_id": "dag1", "is_active": True, "owners": ["me"]}],
        "total_entries": 1,
    }

    mock_response_2 = MagicMock()
    mock_response_2.status_code = 200
    mock_response_2.json.return_value = {"dags": [], "total_entries": 1}

    mock_client = mock_httpx_client.return_value
    mock_client.get.side_effect = [mock_response_1, mock_response_2]

    connector = AirflowConnector(config)
    dags = connector.get_dags()
    assert len(dags) == 1
    assert dags[0].id == "dag1"


@patch("httpx.Client")
def test_airflow_connector_dag_runs(mock_httpx_client):
    config = AirflowConfig(base_url="http://fake", username="u", password="p")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "dag_runs": [
            {
                "dag_id": "dag1",
                "dag_run_id": "run1",
                "state": "success",
                "start_date": "2023-01-01T12:00:00Z",
                "end_date": "2023-01-01T12:30:00Z",
            }
        ]
    }
    mock_client = mock_httpx_client.return_value
    mock_client.get.return_value = mock_response

    connector = AirflowConnector(config)
    runs = connector.get_dag_runs("dag1")
    assert len(runs) == 1
    assert runs[0].state == "success"
    assert runs[0].start_time is not None


@patch("httpx.Client")
def test_airflow_connector_tasks(mock_httpx_client):
    config = AirflowConfig(base_url="http://fake", username="u", password="p")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tasks": [
            {"task_id": "task1", "retries": 3, "ui_color": "#000", "email": ["x@y.com"]}
        ]
    }
    mock_client = mock_httpx_client.return_value
    mock_client.get.return_value = mock_response

    connector = AirflowConnector(config)
    tasks = connector.get_tasks("dag1")
    assert len(tasks) == 1
    assert tasks[0].task_id == "task1"
    assert tasks[0].retries == 3
    assert tasks[0].has_alerts is True
