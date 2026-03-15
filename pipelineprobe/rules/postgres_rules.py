from typing import List, Dict, Any
from pipelineprobe.models import Issue

def check_large_tables(context: dict) -> List[Issue]:
    issues = []
    tables: List[Dict[str, Any]] = context.get("postgres_tables", [])
    for table in tables:
        if table.get("row_count", 0) > 10_000_000:
            issues.append(
                Issue(
                    severity="warning",
                    category="warehouse",
                    summary=f"Table '{table.get('tablename')}' in schema '{table.get('schemaname')}' is very large.",
                    details=f"Row count: {table.get('row_count')}.",
                    recommendation="Consider partitioning the table to improve query performance.",
                    affected_resources=[table.get('tablename')]
                )
            )
    return issues

def check_missing_timestamps(context: dict) -> List[Issue]:
    issues = []
    tables: List[Dict[str, Any]] = context.get("postgres_tables", [])
    for table in tables:
        # For simplicity, we flag tables > 1,000,000 rows without timestamps
        if table.get("row_count", 0) > 1_000_000 and not table.get("has_timestamps"):
            issues.append(
                Issue(
                    severity="warning",
                    category="warehouse",
                    summary=f"Table '{table.get('tablename')}' in schema '{table.get('schemaname')}' has no updated_at/created_at columns.",
                    details=f"Row count is {table.get('row_count')} but no audit timestamps exist.",
                    recommendation="Add updated_at / created_at columns for incremental ingestion and auditing.",
                    affected_resources=[table.get('tablename')]
                )
            )
    return issues

def register_postgres_rules(engine):
    engine.register_rule(check_large_tables)
    engine.register_rule(check_missing_timestamps)
