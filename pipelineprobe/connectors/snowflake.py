import logging
from typing import Any, Dict, List

import snowflake.connector

from pipelineprobe.config import WarehouseConfig

logger = logging.getLogger(__name__)


class SnowflakeConnector:
    def __init__(self, config: WarehouseConfig):
        self.config = config

    def get_stats_sync(self) -> List[Dict[str, Any]]:
        # Validate required credentials before attempting connection
        missing = [
            field
            for field, val in [
                ("account", self.config.account),
                ("username", self.config.username),
                ("password", self.config.password),
            ]
            if not val
        ]
        if missing:
            logger.error(
                "Snowflake connector is missing required config fields: %s. "
                "Set them in pipelineprobe.yml under warehouse.account / username / password.",
                ", ".join(missing),
            )
            return []

        try:
            conn = snowflake.connector.connect(
                user=self.config.username,
                password=self.config.password,
                account=self.config.account,
            )
            cursor = conn.cursor()
            # Snowflake INFORMATION_SCHEMA.TABLES has ROW_COUNT — no subquery join needed
            # because Snowflake forbids correlated subqueries there. Use a CTE instead.
            query = """
                WITH ts_cols AS (
                    SELECT TABLE_SCHEMA, TABLE_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE UPPER(COLUMN_NAME) IN ('UPDATED_AT', 'CREATED_AT')
                      AND TABLE_SCHEMA != 'INFORMATION_SCHEMA'
                    GROUP BY TABLE_SCHEMA, TABLE_NAME
                )
                SELECT
                    t.TABLE_SCHEMA  AS schemaname,
                    t.TABLE_NAME    AS tablename,
                    t.ROW_COUNT     AS row_count,
                    (tc.TABLE_NAME IS NOT NULL) AS has_timestamps
                FROM INFORMATION_SCHEMA.TABLES t
                LEFT JOIN ts_cols tc
                    ON UPPER(tc.TABLE_SCHEMA) = UPPER(t.TABLE_SCHEMA)
                   AND UPPER(tc.TABLE_NAME)   = UPPER(t.TABLE_NAME)
                WHERE t.TABLE_SCHEMA != 'INFORMATION_SCHEMA'
                  AND t.ROW_COUNT IS NOT NULL
                ORDER BY t.ROW_COUNT DESC
                LIMIT 50
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            result = [
                {
                    "schemaname": r[0],
                    "tablename": r[1],
                    "row_count": r[2] or 0,
                    "has_timestamps": bool(r[3]),
                }
                for r in rows
            ]
            cursor.close()
            conn.close()
            return result
        except Exception as e:
            logger.error("Error connecting to Snowflake: %s", e)
            return []

    def get_cost_insights_sync(self) -> List[Dict[str, Any]]:
        """Return credit consumption per warehouse over the past 30 days.

        Queries ``SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY``, which is
        available in all Snowflake accounts with ACCOUNTADMIN (or equivalent).

        Returns a list of dicts with keys:
            warehouse_name  str   — Snowflake virtual warehouse name
            total_credits   float — credits consumed in the last 30 days
            cloud_services  float — cloud-services credits (subset of total)
        """
        missing = [
            field
            for field, val in [
                ("account", self.config.account),
                ("username", self.config.username),
                ("password", self.config.password),
            ]
            if not val
        ]
        if missing:
            logger.error(
                "Snowflake cost insights: missing required config fields: %s",
                ", ".join(missing),
            )
            return []

        try:
            conn = snowflake.connector.connect(
                user=self.config.username,
                password=self.config.password,
                account=self.config.account,
            )
            cursor = conn.cursor()
            query = """
                SELECT
                    WAREHOUSE_NAME,
                    SUM(CREDITS_USED)               AS total_credits,
                    SUM(CREDITS_USED_CLOUD_SERVICES) AS cloud_services
                FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
                WHERE START_TIME >= DATEADD(DAY, -30, CURRENT_TIMESTAMP())
                GROUP BY WAREHOUSE_NAME
                ORDER BY total_credits DESC
                LIMIT 25
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            result = [
                {
                    "warehouse_name": r[0],
                    "total_credits": float(r[1] or 0),
                    "cloud_services": float(r[2] or 0),
                }
                for r in rows
            ]
            cursor.close()
            conn.close()
            return result
        except Exception as e:
            logger.error("Error fetching Snowflake cost insights: %s", e)
            return []
