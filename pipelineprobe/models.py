from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel


class DagRun(BaseModel):
    state: str
    start_time: datetime
    end_time: datetime | None = None


class Dag(BaseModel):
    id: str
    is_active: bool
    recent_runs: list[DagRun]
    owner: str | None = None


class Task(BaseModel):
    dag_id: str
    task_id: str
    retries: int
    sla: timedelta | None = None
    has_alerts: bool


class DbtModel(BaseModel):
    name: str
    tests_count: int
    last_run_status: str
    tags: list[str]


class Issue(BaseModel):
    severity: Literal["critical", "warning", "info"]
    category: Literal["dag", "task", "dbt", "warehouse"]
    summary: str
    details: str
    recommendation: str
    affected_resources: list[str]
