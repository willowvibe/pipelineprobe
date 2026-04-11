"""Cost-insight rules for v0.3.0.

These rules operate on data fetched by the ``get_cost_insights_sync()`` methods
added to :class:`~pipelineprobe.connectors.bigquery.BigQueryConnector` and
:class:`~pipelineprobe.connectors.snowflake.SnowflakeConnector`.

Context keys consumed:
    bq_cost_insights    List[dict]  — from BigQueryConnector.get_cost_insights_sync()
    sf_cost_insights    List[dict]  — from SnowflakeConnector.get_cost_insights_sync()
"""

from typing import Any, Dict, List

from pipelineprobe.models import Issue

# Thresholds — intentionally conservative defaults so that the rules are
# actionable for small and large organisations alike.
_BQ_WARN_GB = 500  # warn when a table accounts for >= 500 GiB billed / 30 days
_BQ_CRIT_GB = 5_000  # critical when >= 5 TiB billed
_SF_WARN_CREDITS = 500  # warn when a warehouse consumes >= 500 credits / 30 days
_SF_CRIT_CREDITS = 5_000  # critical when >= 5 000 credits


def check_expensive_bq_tables(context: dict) -> List[Issue]:
    """Flag BigQuery tables with disproportionately high bytes billed.

    Only runs when ``warehouse_type == "bigquery"`` **and** BQ cost data is
    present in the context, so the rule is a no-op for other warehouse types.
    """
    if context.get("warehouse_type") != "bigquery":
        return []

    insights: List[Dict[str, Any]] = context.get("bq_cost_insights", [])
    if not insights:
        return []

    issues: List[Issue] = []
    for row in insights:
        table_id: str = row.get("table_id", "<unknown>")
        gb: float = row.get("total_gb_billed", 0.0)
        queries: int = row.get("query_count", 0)

        if gb >= _BQ_CRIT_GB:
            issues.append(
                Issue(
                    severity="critical",
                    category="warehouse",
                    summary=f"BigQuery table '{table_id}' billed {gb:,.1f} GiB over 30 days.",
                    details=(
                        f"This table was referenced in {queries} queries and "
                        f"caused {gb:,.1f} GiB of bytes billed in the last 30 days "
                        f"(threshold: {_BQ_CRIT_GB:,} GiB)."
                    ),
                    recommendation=(
                        "Partition or cluster the table, add WHERE filters on partition "
                        "columns, or cache frequently-queried intermediate results."
                    ),
                    affected_resources=[table_id],
                )
            )
        elif gb >= _BQ_WARN_GB:
            issues.append(
                Issue(
                    severity="warning",
                    category="warehouse",
                    summary=f"BigQuery table '{table_id}' billed {gb:,.1f} GiB over 30 days.",
                    details=(
                        f"This table was referenced in {queries} queries and "
                        f"caused {gb:,.1f} GiB of bytes billed in the last 30 days "
                        f"(threshold: {_BQ_WARN_GB:,} GiB)."
                    ),
                    recommendation=(
                        "Review queries against this table for missing partition filters. "
                        "Consider clustering or materialising expensive transformations."
                    ),
                    affected_resources=[table_id],
                )
            )

    return issues


def check_snowflake_credit_spenders(context: dict) -> List[Issue]:
    """Flag Snowflake virtual warehouses with high credit consumption.

    Only runs when ``warehouse_type == "snowflake"`` **and** Snowflake cost
    data is present in the context.
    """
    if context.get("warehouse_type") != "snowflake":
        return []

    insights: List[Dict[str, Any]] = context.get("sf_cost_insights", [])
    if not insights:
        return []

    issues: List[Issue] = []
    for row in insights:
        wh_name: str = row.get("warehouse_name", "<unknown>")
        credits: float = row.get("total_credits", 0.0)
        cloud_svc: float = row.get("cloud_services", 0.0)

        if credits >= _SF_CRIT_CREDITS:
            issues.append(
                Issue(
                    severity="critical",
                    category="warehouse",
                    summary=(
                        f"Snowflake warehouse '{wh_name}' consumed "
                        f"{credits:,.1f} credits over 30 days."
                    ),
                    details=(
                        f"Total credits: {credits:,.1f} "
                        f"(cloud services: {cloud_svc:,.1f}). "
                        f"Threshold: {_SF_CRIT_CREDITS:,} credits."
                    ),
                    recommendation=(
                        "Right-size the warehouse (reduce size or enable auto-suspend), "
                        "audit long-running queries, and consider dedicated warehouses "
                        "per workload to limit blast radius."
                    ),
                    affected_resources=[wh_name],
                )
            )
        elif credits >= _SF_WARN_CREDITS:
            issues.append(
                Issue(
                    severity="warning",
                    category="warehouse",
                    summary=(
                        f"Snowflake warehouse '{wh_name}' consumed "
                        f"{credits:,.1f} credits over 30 days."
                    ),
                    details=(
                        f"Total credits: {credits:,.1f} "
                        f"(cloud services: {cloud_svc:,.1f}). "
                        f"Threshold: {_SF_WARN_CREDITS:,} credits."
                    ),
                    recommendation=(
                        "Review auto-suspend settings and query patterns. "
                        "Caching repeated results and auto-scaling can reduce spend."
                    ),
                    affected_resources=[wh_name],
                )
            )

    return issues


def register_cost_rules(engine) -> None:
    engine.register_rule(check_expensive_bq_tables)
    engine.register_rule(check_snowflake_credit_spenders)
