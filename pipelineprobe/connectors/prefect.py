import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from pipelineprobe.config import AirflowConfig
from pipelineprobe.models import Dag, DagRun, Task

logger = logging.getLogger(__name__)

# Prefect flow-run state → canonical state used by existing rules
_STATE_MAP = {
    "COMPLETED": "success",
    "FAILED": "failed",
    "CRASHED": "failed",
    "CANCELLED": "skipped",
    "CANCELLING": "running",
    "RUNNING": "running",
    "PENDING": "queued",
    "SCHEDULED": "queued",
    "PAUSED": "running",
}

_MAX_RUNS_PER_FLOW = 20  # how many recent runs to fetch per flow
_FLOWS_PAGE_LIMIT = 200  # how many flows to fetch per request


class PrefectConnector:
    """Connector for Prefect 2/3 (Server or Cloud).

    Configuration via the orchestrator section of pipelineprobe.yml:

        orchestrator:
          type: prefect
          base_url: "http://localhost:4200"      # Prefect Server
          # For Prefect Cloud set base_url to the workspace REST endpoint:
          # base_url: "https://api.prefect.cloud/api/accounts/<ACCOUNT_ID>/workspaces/<WORKSPACE_ID>"
          api_key: "<your-prefect-api-key>"      # omit for local Server
          verify_ssl: true
          lookback_days: 14
    """

    def __init__(self, config: AirflowConfig) -> None:
        self.config = config
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        self.client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            headers=headers,
            verify=config.verify_ssl,
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Public interface (mirrors AirflowConnector)
    # ------------------------------------------------------------------

    def get_dags(self) -> List[Dag]:
        """Fetch all Prefect flows and their recent runs.

        Returns a list of :class:`~pipelineprobe.models.Dag` objects so that
        the existing Airflow rules (high failure rate, stale DAGs, …) can run
        against Prefect flows without modification.
        """
        flows = self._fetch_flows()
        dags: List[Dag] = []
        for flow in flows:
            flow_id: str = flow.get("id", "")
            flow_name: str = flow.get("name", flow_id)
            runs = self._fetch_flow_runs(flow_id)
            dags.append(
                Dag(
                    id=flow_name,
                    is_active=True,  # Prefect doesn't have a first-class "active" flag
                    recent_runs=runs,
                    owner=None,
                )
            )
        return dags

    def get_tasks(self, flow_id: str) -> List[Task]:
        """Prefect tasks are ephemeral Python function calls; no static config
        is exposed via the REST API.  Return an empty list so task-level rules
        are skipped gracefully."""
        return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_flows(self) -> List[Dict[str, Any]]:
        try:
            payload: Dict[str, Any] = {
                "limit": _FLOWS_PAGE_LIMIT,
                "offset": 0,
                "sort": "CREATED_DESC",
            }
            resp = self.client.post("/api/flows/filter", json=payload)
            resp.raise_for_status()
            return resp.json() or []
        except Exception as exc:
            logger.error("PrefectConnector: error fetching flows: %s", exc)
            return []

    def _fetch_flow_runs(self, flow_id: str) -> List[DagRun]:
        try:
            payload: Dict[str, Any] = {
                "flow_runs": {"flow_id": {"any_": [flow_id]}},
                "limit": _MAX_RUNS_PER_FLOW,
                "sort": "START_TIME_DESC",
            }
            resp = self.client.post("/api/flow_runs/filter", json=payload)
            resp.raise_for_status()
            raw_runs: List[Dict[str, Any]] = resp.json() or []
            return [self._parse_run(r) for r in raw_runs]
        except Exception as exc:
            logger.error(
                "PrefectConnector: error fetching runs for flow %s: %s", flow_id, exc
            )
            return []

    @staticmethod
    def _parse_run(raw: Dict[str, Any]) -> DagRun:
        state_name: str = (raw.get("state") or {}).get("type", "UNKNOWN")
        state = _STATE_MAP.get(state_name.upper(), "unknown")

        start_time = _parse_prefect_dt(raw.get("start_time") or raw.get("expected_start_time"))
        end_time = _parse_prefect_dt(raw.get("end_time"))

        return DagRun(state=state, start_time=start_time, end_time=end_time)


def _parse_prefect_dt(value: Optional[str]) -> datetime:
    """Parse an ISO-8601 string from the Prefect API into a timezone-aware datetime.

    Falls back to now (UTC) so that :class:`~pipelineprobe.models.DagRun` always
    has a valid ``start_time``.
    """
    if value:
        try:
            from dateutil.parser import parse as _parse

            dt = _parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return datetime.now(timezone.utc)
