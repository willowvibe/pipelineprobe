"""Tests for v0.3.0 cost-insight rules."""

from pipelineprobe.rules.cost_rules import (
    check_expensive_bq_tables,
    check_snowflake_credit_spenders,
)


# ---------------------------------------------------------------------------
# BigQuery cost rules
# ---------------------------------------------------------------------------


class TestExpensiveBqTables:
    def test_skips_non_bigquery(self):
        context = {
            "warehouse_type": "postgres",
            "bq_cost_insights": [
                {"table_id": "p.d.t", "total_bytes_billed": 999_999_999_999, "total_gb_billed": 930.0, "query_count": 5}
            ],
        }
        assert check_expensive_bq_tables(context) == []

    def test_skips_empty_insights(self):
        context = {"warehouse_type": "bigquery", "bq_cost_insights": []}
        assert check_expensive_bq_tables(context) == []

    def test_no_issues_below_threshold(self):
        context = {
            "warehouse_type": "bigquery",
            "bq_cost_insights": [
                {"table_id": "p.d.small", "total_bytes_billed": 1_073_741_824, "total_gb_billed": 1.0, "query_count": 10}
            ],
        }
        issues = check_expensive_bq_tables(context)
        assert issues == []

    def test_warning_at_warn_threshold(self):
        context = {
            "warehouse_type": "bigquery",
            "bq_cost_insights": [
                # 600 GiB → warn (>= 500 GiB, < 5000 GiB)
                {"table_id": "p.d.medium_table", "total_bytes_billed": 644_245_094_400, "total_gb_billed": 600.0, "query_count": 50}
            ],
        }
        issues = check_expensive_bq_tables(context)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "p.d.medium_table" in issues[0].affected_resources

    def test_critical_at_crit_threshold(self):
        context = {
            "warehouse_type": "bigquery",
            "bq_cost_insights": [
                # 6000 GiB → critical (>= 5000 GiB)
                {"table_id": "p.d.huge_table", "total_bytes_billed": 6_442_450_944_000, "total_gb_billed": 6000.0, "query_count": 500}
            ],
        }
        issues = check_expensive_bq_tables(context)
        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert "p.d.huge_table" in issues[0].affected_resources

    def test_mixed_thresholds(self):
        context = {
            "warehouse_type": "bigquery",
            "bq_cost_insights": [
                {"table_id": "p.d.a", "total_bytes_billed": 5_000 * 1024**3, "total_gb_billed": 5000.0, "query_count": 100},
                {"table_id": "p.d.b", "total_bytes_billed": 600 * 1024**3, "total_gb_billed": 600.0, "query_count": 20},
                {"table_id": "p.d.c", "total_bytes_billed": 10 * 1024**3, "total_gb_billed": 10.0, "query_count": 5},
            ],
        }
        issues = check_expensive_bq_tables(context)
        assert len(issues) == 2
        severities = {i.affected_resources[0]: i.severity for i in issues}
        assert severities["p.d.a"] == "critical"
        assert severities["p.d.b"] == "warning"


# ---------------------------------------------------------------------------
# Snowflake cost rules
# ---------------------------------------------------------------------------


class TestSnowflakeCreditSpenders:
    def test_skips_non_snowflake(self):
        context = {
            "warehouse_type": "bigquery",
            "sf_cost_insights": [
                {"warehouse_name": "WH", "total_credits": 9999.0, "cloud_services": 100.0}
            ],
        }
        assert check_snowflake_credit_spenders(context) == []

    def test_skips_empty_insights(self):
        context = {"warehouse_type": "snowflake", "sf_cost_insights": []}
        assert check_snowflake_credit_spenders(context) == []

    def test_no_issues_below_threshold(self):
        context = {
            "warehouse_type": "snowflake",
            "sf_cost_insights": [
                {"warehouse_name": "SMALL_WH", "total_credits": 100.0, "cloud_services": 5.0}
            ],
        }
        assert check_snowflake_credit_spenders(context) == []

    def test_warning_at_warn_threshold(self):
        context = {
            "warehouse_type": "snowflake",
            "sf_cost_insights": [
                # 750 credits → warn (>= 500, < 5000)
                {"warehouse_name": "MEDIUM_WH", "total_credits": 750.0, "cloud_services": 30.0}
            ],
        }
        issues = check_snowflake_credit_spenders(context)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "MEDIUM_WH" in issues[0].affected_resources

    def test_critical_at_crit_threshold(self):
        context = {
            "warehouse_type": "snowflake",
            "sf_cost_insights": [
                # 6000 credits → critical (>= 5000)
                {"warehouse_name": "BIG_WH", "total_credits": 6000.0, "cloud_services": 200.0}
            ],
        }
        issues = check_snowflake_credit_spenders(context)
        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert "BIG_WH" in issues[0].affected_resources

    def test_multiple_warehouses(self):
        context = {
            "warehouse_type": "snowflake",
            "sf_cost_insights": [
                {"warehouse_name": "GIANT_WH", "total_credits": 8000.0, "cloud_services": 300.0},
                {"warehouse_name": "MED_WH", "total_credits": 600.0, "cloud_services": 20.0},
                {"warehouse_name": "TINY_WH", "total_credits": 50.0, "cloud_services": 2.0},
            ],
        }
        issues = check_snowflake_credit_spenders(context)
        assert len(issues) == 2
        by_name = {i.affected_resources[0]: i for i in issues}
        assert by_name["GIANT_WH"].severity == "critical"
        assert by_name["MED_WH"].severity == "warning"
        assert "TINY_WH" not in by_name
