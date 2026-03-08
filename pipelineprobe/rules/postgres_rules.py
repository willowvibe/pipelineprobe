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

def register_postgres_rules(engine):
    engine.register_rule(check_large_tables)
