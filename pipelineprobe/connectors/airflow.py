import logging
from datetime import timedelta
from typing import List

import httpx
from dateutil.parser import parse as parse_date

from pipelineprobe.config import AirflowConfig
from pipelineprobe.models import Dag, DagRun, Task

logger = logging.getLogger(__name__)

AIRFLOW_PAGE_LIMIT = 100  # Airflow API max per page


class AirflowConnector:
    def __init__(self, config: AirflowConfig):
        self.config = config
        self.client = httpx.Client(
            base_url=self.config.base_url,
            auth=(self.config.username, self.config.password),
            verify=self.config.verify_ssl,
        )

    def get_dags(self) -> List[Dag]:
        """Fetches all active DAGs from Airflow, handling pagination."""
        dags = []
        offset = 0
        try:
            while True:
                response = self.client.get(
                    "/api/v1/dags",
                    params={"limit": AIRFLOW_PAGE_LIMIT, "offset": offset},
                )
                response.raise_for_status()
                body = response.json()
                page = body.get("dags", [])
                for d in page:
                    dags.append(
                        Dag(
                            id=d.get("dag_id", ""),
                            is_active=d.get("is_active", False),
                            recent_runs=[],
                            owner=d.get("owners", [])[0] if d.get("owners") else None,
                        )
                    )
                # Stop if we got fewer results than the page limit — last page
                if len(page) < AIRFLOW_PAGE_LIMIT:
                    break
                offset += AIRFLOW_PAGE_LIMIT
        except Exception as e:
            logger.error("Error fetching DAGs from Airflow: %s", e)
        return dags

    def get_dag_runs(self, dag_id: str) -> List[DagRun]:
        """Fetches the most recent runs for a given DAG."""
        try:
            response = self.client.get(
                f"/api/v1/dags/{dag_id}/dagRuns",
                params={"limit": 20, "order_by": "-execution_date"},
            )
            response.raise_for_status()
            runs_data = response.json().get("dag_runs", [])
            runs = []
            for r in runs_data:
                state = r.get("state", "unknown")
                start_str = r.get("start_date")
                end_str = r.get("end_date")
                # Fall back to execution_date if start_date missing (older Airflow versions)
                start_time = parse_date(start_str) if start_str else parse_date(r["execution_date"])
                end_time = parse_date(end_str) if end_str else None
                runs.append(DagRun(state=state, start_time=start_time, end_time=end_time))
            return runs
        except Exception as e:
            logger.error("Error fetching DAG runs for %s: %s", dag_id, e)
            return []

    def get_tasks(self, dag_id: str) -> List[Task]:
        """Fetches task configurations for a given DAG."""
        try:
            response = self.client.get(f"/api/v1/dags/{dag_id}/tasks")
            response.raise_for_status()
            tasks_data = response.json().get("tasks", [])
            tasks = []
            for t in tasks_data:
                retries = t.get("retries", 0)
                has_sla = bool(t.get("sla"))
                # Store SLA presence as a non-zero timedelta; exact value is not used in rules
                sla_val = timedelta(seconds=1) if has_sla else None
                # email_on_failure / email fields indicate some alerting is configured
                has_alerts = bool(t.get("email")) or bool(t.get("email_on_failure"))
                tasks.append(
                    Task(
                        dag_id=dag_id,
                        task_id=t.get("task_id", ""),
                        retries=int(retries) if retries is not None else 0,
                        sla=sla_val,
                        has_alerts=has_alerts,
                    )
                )
            return tasks
        except Exception as e:
            logger.error("Error fetching tasks for %s: %s", dag_id, e)
            return []
