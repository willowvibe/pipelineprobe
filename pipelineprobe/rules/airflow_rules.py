from typing import List
from datetime import datetime, timezone
from pipelineprobe.models import Task, Issue, Dag

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

def check_high_failure_rate(context: dict) -> List[Issue]:
    issues = []
    dags: List[Dag] = context.get("airflow_dags", [])
    for dag in dags:
        if not dag.is_active or not dag.recent_runs:
            continue
            
        total_runs = len(dag.recent_runs)
        if total_runs >= 5:
            failed_runs = sum(1 for run in dag.recent_runs if run.state == "failed")
            failure_ratio = failed_runs / total_runs
            if failure_ratio > 0.2:
                issues.append(
                    Issue(
                        severity="critical",
                        category="dag",
                        summary=f"DAG {dag.id} has a high failure rate ({failure_ratio:.0%}).",
                        details=f"{failed_runs} out of the last {total_runs} runs failed.",
                        recommendation="Investigate the root cause of the frequent failures.",
                        affected_resources=[dag.id]
                    )
                )
    return issues


def check_stale_dags(context: dict) -> List[Issue]:
    issues = []
    dags: List[Dag] = context.get("airflow_dags", [])
    # Default stale threshold is 7 days, could be configurable later
    stale_threshold_days = 7
    now = datetime.now(timezone.utc)
    
    for dag in dags:
        if not dag.is_active:
            continue
            
        # A DAG with no recent runs at all is inherently stale
        if not dag.recent_runs:
            issues.append(
                Issue(
                    severity="warning",
                    category="dag",
                    summary=f"DAG {dag.id} has no recent runs recorded.",
                    details="The DAG is active but has never run (or runs were not retrieved).",
                    recommendation="Verify the scheduler is processing this DAG correctly.",
                    affected_resources=[dag.id]
                )
            )
            continue

        # Check if there is any successful run in recent_runs
        recent_successes = [run for run in dag.recent_runs if run.state == "success" and run.end_time]
        
        if recent_successes:
            # Sort by end_time descending to get latest
            latest_success = sorted(recent_successes, key=lambda r: r.end_time, reverse=True)[0]
            end_time_aware = latest_success.end_time
            if end_time_aware.tzinfo is None:
                end_time_aware = end_time_aware.replace(tzinfo=timezone.utc)
                
            days_since = (now - end_time_aware).days
            if days_since > stale_threshold_days:
                issues.append(
                    Issue(
                        severity="warning",
                        category="dag",
                        summary=f"DAG {dag.id} is stale.",
                        details=f"No successful execution in the last {days_since} days.",
                        recommendation="Check if the DAG is still needed, or if it is silently failing to schedule.",
                        affected_resources=[dag.id]
                    )
                )
    return issues

def register_airflow_rules(engine):
    engine.register_rule(check_missing_retries)
    engine.register_rule(check_missing_slas)
    engine.register_rule(check_high_failure_rate)
    engine.register_rule(check_stale_dags)
