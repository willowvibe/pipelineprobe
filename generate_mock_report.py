from pipelineprobe.renderer import ReportRenderer
from pipelineprobe.models import Issue

issues = [
    Issue(
        severity="critical",
        category="dag",
        summary="DAG 'daily_sales_pipeline' has a high failure rate (40%).",
        details="4 out of the last 10 runs failed.",
        recommendation="Investigate the root cause of the frequent failures.",
        affected_resources=["daily_sales_pipeline"]
    ),
    Issue(
        severity="critical",
        category="dbt",
        summary="dbt model 'fact_mrr' failed in the last run.",
        details="Last run status: error",
        recommendation="Investigate and fix the failing model or tests.",
        affected_resources=["fact_mrr"]
    ),
    Issue(
        severity="warning",
        category="warehouse",
        summary="Table 'stg_events' in schema 'raw' has no updated_at/created_at columns.",
        details="Row count is 58400000 but no audit timestamps exist.",
        recommendation="Add updated_at / created_at columns for incremental ingestion and auditing.",
        affected_resources=["stg_events"]
    ),
    Issue(
        severity="warning",
        category="task",
        summary="Task 'extract_salesforce' in DAG 'crm_sync' has no retries configured.",
        details="Tasks without retries are more prone to transient failures.",
        recommendation="Configure at least 1-3 retries for the task.",
        affected_resources=["extract_salesforce"]
    )
]

summary = {
    "score": 76,
    "critical_count": 2,
    "warning_count": 2,
    "total_issues": 4
}

renderer = ReportRenderer("reports")
renderer.render_html(issues, summary)
print("Mock report generated at reports/pipelineprobe-report.html")
