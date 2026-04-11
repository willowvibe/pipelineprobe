"""Tests for Prefect and Dagster connectors (v0.2.0) and cost-insight
connector methods on BigQuery and Snowflake (v0.3.0)."""

from unittest.mock import MagicMock, patch

import pytest

from pipelineprobe.config import AirflowConfig, WarehouseConfig
from pipelineprobe.connectors.prefect import PrefectConnector
from pipelineprobe.connectors.dagster import DagsterConnector
from pipelineprobe.connectors.bigquery import BigQueryConnector
from pipelineprobe.connectors.snowflake import SnowflakeConnector


# ---------------------------------------------------------------------------
# Prefect connector
# ---------------------------------------------------------------------------


class TestPrefectConnector:
    def _config(self, **kwargs) -> AirflowConfig:
        defaults = dict(type="prefect", base_url="http://prefect:4200", api_key=None)
        defaults.update(kwargs)
        return AirflowConfig(**defaults)

    @patch("pipelineprobe.connectors.prefect.httpx.Client")
    def test_get_dags_success(self, mock_client_cls):
        config = self._config()
        connector = PrefectConnector(config)

        # The connector does not use a context manager — grab the instance directly
        mock_client_instance = mock_client_cls.return_value

        # Stub flows response
        flows_resp = MagicMock()
        flows_resp.raise_for_status.return_value = None
        flows_resp.json.return_value = [
            {"id": "flow-uuid-1", "name": "etl_flow"},
            {"id": "flow-uuid-2", "name": "ml_pipeline"},
        ]

        # Stub flow-runs response (same response for both flows)
        runs_resp = MagicMock()
        runs_resp.raise_for_status.return_value = None
        runs_resp.json.return_value = [
            {
                "id": "run-1",
                "state": {"type": "COMPLETED"},
                "start_time": "2026-04-01T10:00:00+00:00",
                "end_time": "2026-04-01T10:30:00+00:00",
            },
            {
                "id": "run-2",
                "state": {"type": "FAILED"},
                "start_time": "2026-04-02T08:00:00+00:00",
                "end_time": None,
            },
        ]

        mock_client_instance.post.side_effect = [
            flows_resp,  # /api/flows/filter
            runs_resp,  # /api/flow_runs/filter for flow-uuid-1
            runs_resp,  # /api/flow_runs/filter for flow-uuid-2
        ]

        dags = connector.get_dags()

        assert len(dags) == 2
        assert dags[0].id == "etl_flow"
        assert dags[1].id == "ml_pipeline"
        # Both flows have 2 runs
        assert len(dags[0].recent_runs) == 2
        assert dags[0].recent_runs[0].state == "success"
        assert dags[0].recent_runs[1].state == "failed"

    @patch("pipelineprobe.connectors.prefect.httpx.Client")
    def test_get_dags_api_error_returns_empty(self, mock_client_cls):
        config = self._config()
        connector = PrefectConnector(config)

        mock_client_instance = mock_client_cls.return_value
        mock_client_instance.post.side_effect = Exception("network error")

        dags = connector.get_dags()
        assert dags == []

    @patch("pipelineprobe.connectors.prefect.httpx.Client")
    def test_api_key_sets_auth_header(self, mock_client_cls):
        config = self._config(api_key="secret-token")
        PrefectConnector(config)
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer secret-token"

    def test_get_tasks_returns_empty(self):
        config = self._config()
        connector = PrefectConnector(config)
        assert connector.get_tasks("any-flow-id") == []

    def test_state_mapping(self):
        from pipelineprobe.connectors.prefect import _STATE_MAP

        assert _STATE_MAP["COMPLETED"] == "success"
        assert _STATE_MAP["FAILED"] == "failed"
        assert _STATE_MAP["CRASHED"] == "failed"
        assert _STATE_MAP["CANCELLED"] == "skipped"
        assert _STATE_MAP["RUNNING"] == "running"


# ---------------------------------------------------------------------------
# Dagster connector
# ---------------------------------------------------------------------------


class TestDagsterConnector:
    def _config(self, **kwargs) -> AirflowConfig:
        defaults = dict(type="dagster", base_url="http://dagster:3000", api_key=None)
        defaults.update(kwargs)
        return AirflowConfig(**defaults)

    def _runs_response(self, runs):
        return {
            "data": {
                "runsOrError": {
                    "__typename": "Runs",
                    "results": runs,
                }
            }
        }

    @patch("pipelineprobe.connectors.dagster.httpx.Client")
    def test_get_dags_groups_by_job(self, mock_client_cls):
        config = self._config()
        connector = DagsterConnector(config)

        mock_client = mock_client_cls.return_value
        page = self._runs_response(
            [
                {
                    "runId": "r1",
                    "jobName": "daily_etl",
                    "pipelineName": "daily_etl",
                    "status": "SUCCESS",
                    "startTime": 1_700_000_000.0,
                    "endTime": 1_700_001_000.0,
                },
                {
                    "runId": "r2",
                    "jobName": "daily_etl",
                    "pipelineName": "daily_etl",
                    "status": "FAILURE",
                    "startTime": 1_700_100_000.0,
                    "endTime": 1_700_101_000.0,
                },
                {
                    "runId": "r3",
                    "jobName": "ml_train",
                    "pipelineName": "ml_train",
                    "status": "SUCCESS",
                    "startTime": 1_700_200_000.0,
                    "endTime": None,
                },
            ]
        )
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = page
        # Return empty page on second call to stop pagination
        empty_resp = MagicMock()
        empty_resp.raise_for_status.return_value = None
        empty_resp.json.return_value = self._runs_response([])
        mock_client.post.side_effect = [resp, empty_resp]

        dags = connector.get_dags()

        assert len(dags) == 2
        dag_ids = {d.id for d in dags}
        assert dag_ids == {"daily_etl", "ml_train"}

        daily = next(d for d in dags if d.id == "daily_etl")
        assert len(daily.recent_runs) == 2
        assert daily.recent_runs[0].state == "success"
        assert daily.recent_runs[1].state == "failed"

    @patch("pipelineprobe.connectors.dagster.httpx.Client")
    def test_get_dags_error_returns_empty(self, mock_client_cls):
        config = self._config()
        connector = DagsterConnector(config)

        mock_client = mock_client_cls.return_value
        mock_client.post.side_effect = Exception("graphql error")

        dags = connector.get_dags()
        assert dags == []

    @patch("pipelineprobe.connectors.dagster.httpx.Client")
    def test_runsOrError_error_typename(self, mock_client_cls):
        config = self._config()
        connector = DagsterConnector(config)

        mock_client = mock_client_cls.return_value
        err_resp = MagicMock()
        err_resp.raise_for_status.return_value = None
        err_resp.json.return_value = {
            "data": {
                "runsOrError": {
                    "__typename": "PythonError",
                    "message": "something went wrong",
                }
            }
        }
        mock_client.post.return_value = err_resp

        dags = connector.get_dags()
        assert dags == []

    @patch("pipelineprobe.connectors.dagster.httpx.Client")
    def test_api_key_sets_dagster_header(self, mock_client_cls):
        config = self._config(api_key="dag-token")
        DagsterConnector(config)
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs["headers"]["Dagster-Cloud-Api-Token"] == "dag-token"

    def test_get_tasks_returns_empty(self):
        config = self._config()
        connector = DagsterConnector(config)
        assert connector.get_tasks("any-job") == []


# ---------------------------------------------------------------------------
# BigQuery cost insights
# ---------------------------------------------------------------------------


class TestBigQueryCostInsights:
    @patch("pipelineprobe.connectors.bigquery.bigquery.Client")
    def test_get_cost_insights_success(self, mock_client_cls):
        config = WarehouseConfig(type="bigquery", project_id="my_proj")
        connector = BigQueryConnector(config)

        mock_client = mock_client_cls.return_value
        mock_client.project = "my_proj"

        class MockRow:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        mock_job = MagicMock()
        mock_job.result.return_value = [
            MockRow(
                table_id="my_proj.ds.big_table",
                total_bytes_billed=5_368_709_120,  # 5 GiB
                query_count=120,
            ),
        ]
        mock_client.query.return_value = mock_job

        results = connector.get_cost_insights_sync()

        assert len(results) == 1
        row = results[0]
        assert row["table_id"] == "my_proj.ds.big_table"
        assert row["total_bytes_billed"] == 5_368_709_120
        assert row["total_gb_billed"] == pytest.approx(5.0, abs=0.1)
        assert row["query_count"] == 120

    @patch("pipelineprobe.connectors.bigquery.bigquery.Client")
    def test_get_cost_insights_error_returns_empty(self, mock_client_cls):
        config = WarehouseConfig(type="bigquery", project_id="proj")
        connector = BigQueryConnector(config)
        mock_client_cls.side_effect = Exception("BQ error")
        assert connector.get_cost_insights_sync() == []


# ---------------------------------------------------------------------------
# Snowflake cost insights
# ---------------------------------------------------------------------------


class TestSnowflakeCostInsights:
    def test_missing_creds_returns_empty(self):
        config = WarehouseConfig(type="snowflake")
        connector = SnowflakeConnector(config)
        assert connector.get_cost_insights_sync() == []

    @patch("pipelineprobe.connectors.snowflake.snowflake.connector.connect")
    def test_get_cost_insights_success(self, mock_connect):
        config = WarehouseConfig(
            type="snowflake", account="acc", username="usr", password="pw"
        )
        connector = SnowflakeConnector(config)

        mock_cursor = mock_connect.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = [
            ("COMPUTE_WH", 1200.5, 50.0),
            ("LOAD_WH", 300.0, 10.0),
        ]

        results = connector.get_cost_insights_sync()

        assert len(results) == 2
        assert results[0]["warehouse_name"] == "COMPUTE_WH"
        assert results[0]["total_credits"] == pytest.approx(1200.5)
        assert results[0]["cloud_services"] == pytest.approx(50.0)
        assert results[1]["warehouse_name"] == "LOAD_WH"

    @patch("pipelineprobe.connectors.snowflake.snowflake.connector.connect")
    def test_get_cost_insights_error_returns_empty(self, mock_connect):
        config = WarehouseConfig(
            type="snowflake", account="acc", username="usr", password="pw"
        )
        connector = SnowflakeConnector(config)
        mock_connect.side_effect = Exception("SF error")
        assert connector.get_cost_insights_sync() == []
