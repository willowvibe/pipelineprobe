from typing import List
from pipelineprobe.models import Task, Issue

def check_missing_retries(context: dict) -> List[Issue]:
    issues = []
    tasks: List[Task] = context.get("airflow_tasks", [])
    for task in tasks:
        if task.retries == 0:
            issues.append(
                Issue(
                    severity="warning",
                    category="task",
                    summary=f"Task {task.task_id} in DAG {task.dag_id} has no retries configured.",
                    details="Tasks without retries are more prone to transient failures.",
                    recommendation="Configure at least 1-3 retries for the task.",
                    affected_resources=[task.task_id]
                )
            )
    return issues

def check_missing_slas(context: dict) -> List[Issue]:
    issues = []
    tasks: List[Task] = context.get("airflow_tasks", [])
    for task in tasks:
        if not task.sla:
            issues.append(
                Issue(
                    severity="info",
                    category="task",
                    summary=f"Task {task.task_id} in DAG {task.dag_id} has no SLA configured.",
                    details="Tasks without SLAs might silently miss deadlines.",
                    recommendation="Configure an SLA if this task is time-sensitive.",
                    affected_resources=[task.task_id]
                )
            )
    return issues

def register_airflow_rules(engine):
    engine.register_rule(check_missing_retries)
    engine.register_rule(check_missing_slas)
