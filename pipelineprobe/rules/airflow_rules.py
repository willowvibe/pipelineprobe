from typing import List
from datetime import datetime, timezone
from pipelineprobe.models import Task, Issue, Dag


def _severity(context: dict, rule_name: str, default: str) -> str:
    """Return the effective severity for a rule, respecting YAML overrides."""
    overrides: dict = context.get("rule_severity_overrides", {})
    return overrides.get(rule_name, default)


def check_missing_retries(context: dict) -> List[Issue]:
    issues = []
    tasks: List[Task] = context.get("airflow_tasks", [])
    sev = _severity(context, "missing_retries", "warning")
    for task in tasks:
        if task.retries == 0:
            issues.append(
                Issue(
                    severity=sev,
                    category="task",
                    summary=f"Task {task.task_id} in DAG {task.dag_id} has no retries configured.",
                    details="Tasks without retries are more prone to transient failures.",
                    recommendation="Configure at least 1-3 retries for the task.",
                    affected_resources=[task.task_id],
                )
            )
    return issues


def check_missing_slas(context: dict) -> List[Issue]:
    issues = []
    tasks: List[Task] = context.get("airflow_tasks", [])
    sev = _severity(context, "missing_sla", "info")
    for task in tasks:
        if not task.sla:
            issues.append(
                Issue(
                    severity=sev,
                    category="task",
                    summary=f"Task {task.task_id} in DAG {task.dag_id} has no SLA configured.",
                    details="Tasks without SLAs might silently miss deadlines.",
                    recommendation="Configure an SLA if this task is time-sensitive.",
                    affected_resources=[task.task_id],
                )
            )
    return issues


def check_high_failure_rate(context: dict) -> List[Issue]:
    issues = []
    dags: List[Dag] = context.get("airflow_dags", [])
    sev = _severity(context, "high_failure_rate", "critical")
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
                        severity=sev,
                        category="dag",
                        summary=f"DAG {dag.id} has a high failure rate ({failure_ratio:.0%}).",
                        details=f"{failed_runs} out of the last {total_runs} runs failed.",
                        recommendation="Investigate the root cause of the frequent failures.",
                        affected_resources=[dag.id],
                    )
                )
    return issues


def check_stale_dags(context: dict) -> List[Issue]:
    issues = []
    dags: List[Dag] = context.get("airflow_dags", [])
    stale_threshold_days: int = context.get("stale_threshold_days", 7)
    sev = _severity(context, "stale_dags", "warning")
    now = datetime.now(timezone.utc)

    for dag in dags:
        if not dag.is_active:
            continue

        # A DAG with no recent runs at all is inherently stale
        if not dag.recent_runs:
            issues.append(
                Issue(
                    severity=sev,
                    category="dag",
                    summary=f"DAG {dag.id} has no recent runs recorded.",
                    details="The DAG is active but has never run (or runs were not retrieved).",
                    recommendation="Verify the scheduler is processing this DAG correctly.",
                    affected_resources=[dag.id],
                )
            )
            continue

        # Check if there is any successful run in recent_runs
        recent_successes = [
            run for run in dag.recent_runs if run.state == "success" and run.end_time
        ]

        if not recent_successes:
            # Has runs but zero successes — flag as critical regardless of override,
            # because this is an active outage signal (override still respected)
            outage_sev = _severity(context, "stale_dags", "critical")
            issues.append(
                Issue(
                    severity=outage_sev,
                    category="dag",
                    summary=f"DAG {dag.id} has no successful runs in its recent history.",
                    details=f"Last {len(dag.recent_runs)} runs all ended in non-success states.",
                    recommendation="Investigate failures immediately — this DAG has never succeeded recently.",
                    affected_resources=[dag.id],
                )
            )
        else:
            # Sort by end_time descending to get latest
            latest_success = sorted(
                recent_successes, key=lambda r: r.end_time, reverse=True
            )[0]
            end_time_aware = latest_success.end_time
            if end_time_aware.tzinfo is None:
                end_time_aware = end_time_aware.replace(tzinfo=timezone.utc)

            days_since = (now - end_time_aware).total_seconds() / 86400
            if days_since > stale_threshold_days:
                issues.append(
                    Issue(
                        severity=sev,
                        category="dag",
                        summary=f"DAG {dag.id} is stale.",
                        details=f"No successful execution in the last {days_since:.1f} days (threshold: {stale_threshold_days}d).",
                        recommendation="Check if the DAG is still needed, or if it is silently failing to schedule.",
                        affected_resources=[dag.id],
                    )
                )
    return issues


def register_airflow_rules(engine):
    engine.register_rule(check_missing_retries)
    engine.register_rule(check_missing_slas)
    engine.register_rule(check_high_failure_rate)
    engine.register_rule(check_stale_dags)
