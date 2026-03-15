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
        try:
            # Fetch last N runs, ordered by execution_date descending
            # Airflow API uses limit for pagination. We fetch top 20 for MVP.
            response = self.client.get(f"/api/v1/dags/{dag_id}/dagRuns", params={"limit": 20, "order_by": "-execution_date"})
            response.raise_for_status()
            runs_data = response.json().get("dag_runs", [])
            runs = []
            
            from dateutil.parser import parse as parse_date
            
            for r in runs_data:
                state = r.get("state", "unknown")
                start_str = r.get("start_date")
                end_str = r.get("end_date")
                
                start_time = parse_date(start_str) if start_str else parse_date(r.get("execution_date"))
                end_time = parse_date(end_str) if end_str else None
                
                runs.append(
                    DagRun(
                        state=state,
                        start_time=start_time,
                        end_time=end_time
                    )
                )
            return runs
        except Exception as e:
            print(f"Error fetching DAG runs for {dag_id}: {e}")
            return []

    def get_tasks(self, dag_id: str) -> List[Task]:
        try:
            response = self.client.get(f"/api/v1/dags/{dag_id}/tasks")
            response.raise_for_status()
            tasks_data = response.json().get("tasks", [])
            tasks = []
            
            from datetime import timedelta
            
            for t in tasks_data:
                retries = t.get("retries", 0)
                # Airflow SLA could be represented in seconds or an ISO 8601 duration string 
                # (if provided via REST depending on Airflow version).
                # For safety, let's treat it gracefully. We'll simplify to checking if it's there.
                # Just checking if SLA is truthy for the MVP.
                has_sla = bool(t.get("sla"))
                sla_val = timedelta(seconds=1) if has_sla else None
                 
                is_email = bool(t.get("email")) # presence of emails means some alerts
                
                tasks.append(
                    Task(
                        dag_id=dag_id,
                        task_id=t.get("task_id", ""),
                        retries=int(retries) if retries is not None else 0,
                        sla=sla_val,
                        has_alerts=is_email
                    )
                )
            return tasks
        except Exception as e:
            print(f"Error fetching tasks for {dag_id}: {e}")
            return []
