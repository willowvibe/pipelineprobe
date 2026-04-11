import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from pipelineprobe.config import AirflowConfig
from pipelineprobe.models import Dag, DagRun, Task

logger = logging.getLogger(__name__)

# Dagster run pipeline_run_status → canonical state used by existing rules
_STATUS_MAP = {
    "SUCCESS": "success",
    "FAILURE": "failed",
    "CANCELED": "skipped",
    "CANCELING": "running",
    "STARTED": "running",
    "STARTING": "running",
    "MANAGED": "running",
    "NOT_STARTED": "queued",
}

_RUNS_LIMIT = 500  # how many runs to pull per request (Dagster paginates by cursor)
_MAX_RUNS_PER_JOB = 20  # how many runs to keep per job after grouping

# GraphQL query — fetches runs for analysis
_RUNS_QUERY = """
query PipelineProbeRuns($limit: Int!, $cursor: String) {
  runsOrError(
    filter: {}
    limit: $limit
    cursor: $cursor
  ) {
    __typename
    ... on Runs {
      results {
        runId
        jobName
        pipelineName
        status
        startTime
        endTime
        tags { key value }
      }
    }
    ... on InvalidPipelineRunsFilterError {
      message
    }
    ... on PythonError {
      message
    }
  }
}
"""


class DagsterConnector:
    """Connector for Dagster (open-source or Dagster Cloud).

    Configuration via the orchestrator section of pipelineprobe.yml:

        orchestrator:
          type: dagster
          base_url: "http://localhost:3000"      # Dagster webserver (local)
          api_key: "<dagster-cloud-token>"        # omit for local
          verify_ssl: true
          lookback_days: 14
    """

    def __init__(self, config: AirflowConfig) -> None:
        self.config = config
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Dagster-Cloud-Api-Token"] = config.api_key
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
        """Fetch recent Dagster runs, group by job, and return as Dag objects.

        Returns a list of :class:`~pipelineprobe.models.Dag` objects so that
        the existing Airflow rules (high failure rate, stale DAGs, …) can run
        against Dagster jobs without modification.
        """
        raw_runs = self._fetch_runs()
        # Group runs by job name
        by_job: Dict[str, List[DagRun]] = defaultdict(list)
        for r in raw_runs:
            job_name = r.get("jobName") or r.get("pipelineName") or "<unknown>"
            if len(by_job[job_name]) < _MAX_RUNS_PER_JOB:
                by_job[job_name].append(self._parse_run(r))

        dags: List[Dag] = []
        for job_name, runs in by_job.items():
            dags.append(
                Dag(
                    id=job_name,
                    is_active=True,  # no first-class "active" concept in Dagster
                    recent_runs=runs,
                    owner=None,
                )
            )
        return dags

    def get_tasks(self, job_name: str) -> List[Task]:
        """Dagster op/task metadata requires per-repo queries and is not needed for
        the current rule set.  Return an empty list so task-level rules are skipped."""
        return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_runs(self) -> List[Dict[str, Any]]:
        """Fetch runs from the Dagster GraphQL API, paginating via cursor."""
        all_runs: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        try:
            while True:
                variables: Dict[str, Any] = {"limit": _RUNS_LIMIT}
                if cursor:
                    variables["cursor"] = cursor

                resp = self.client.post(
                    "/graphql",
                    json={"query": _RUNS_QUERY, "variables": variables},
                )
                resp.raise_for_status()
                body = resp.json()

                runs_or_error = body.get("data", {}).get("runsOrError", {})
                typename = runs_or_error.get("__typename", "")

                if typename != "Runs":
                    msg = runs_or_error.get("message", "unknown error")
                    logger.error(
                        "DagsterConnector: runsOrError returned %s: %s", typename, msg
                    )
                    break

                page: List[Dict[str, Any]] = runs_or_error.get("results", [])
                all_runs.extend(page)

                # Dagster cursor-based pagination: if fewer results than limit, done
                if len(page) < _RUNS_LIMIT:
                    break

                # Use the last runId as the next cursor
                cursor = page[-1].get("runId")
                if not cursor:
                    break

        except Exception as exc:
            logger.error("DagsterConnector: error fetching runs: %s", exc)

        return all_runs

    @staticmethod
    def _parse_run(raw: Dict[str, Any]) -> DagRun:
        status = _STATUS_MAP.get((raw.get("status") or "").upper(), "unknown")
        start_time = _parse_dagster_ts(raw.get("startTime"))
        end_time = _parse_dagster_ts(raw.get("endTime"))
        return DagRun(state=status, start_time=start_time, end_time=end_time)


def _parse_dagster_ts(value: Optional[float]) -> datetime:
    """Convert a Dagster Unix timestamp (float seconds) to a timezone-aware datetime.

    Falls back to now (UTC) so that :class:`~pipelineprobe.models.DagRun` always
    has a valid ``start_time``.
    """
    if value is not None:
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)
