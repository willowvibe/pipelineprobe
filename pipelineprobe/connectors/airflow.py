import httpx
from typing import List
from pipelineprobe.config import AirflowConfig
from pipelineprobe.models import Dag, DagRun, Task

class AirflowConnector:
    def __init__(self, config: AirflowConfig):
        self.config = config
        self.client = httpx.Client(
            base_url=self.config.base_url,
            auth=(self.config.username, self.config.password),
            verify=self.config.verify_ssl,
        )

    def get_dags(self) -> List[Dag]:
        # Stub implementation for MVP
        try:
            response = self.client.get("/api/v1/dags")
            response.raise_for_status()
            dags_data = response.json().get("dags", [])
            dags = []
            for d in dags_data:
                dags.append(
                    Dag(
                        id=d.get("dag_id", ""),
                        is_active=d.get("is_active", False),
                        recent_runs=[],
                        owner=d.get("owners", [])[0] if d.get("owners") else None,
                    )
                )
            return dags
        except Exception as e:
            print(f"Error fetching DAGs from Airflow: {e}")
            return []

    def get_dag_runs(self, dag_id: str) -> List[DagRun]:
        # Stub implementation
        return []

    def get_tasks(self, dag_id: str) -> List[Task]:
        # Stub implementation
        return []
