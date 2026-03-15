import logging
from typing import Any, Dict, List

from google.cloud import bigquery

from pipelineprobe.config import WarehouseConfig

logger = logging.getLogger(__name__)


class BigQueryConnector:
    def __init__(self, config: WarehouseConfig):
        self.config = config

    def get_stats_sync(self) -> List[Dict[str, Any]]:
        try:
            client = (
                bigquery.Client(project=self.config.project_id)
                if self.config.project_id
                else bigquery.Client()
            )

            project = client.project  # resolved project for INFORMATION_SCHEMA queries

            # Query TABLE_STORAGE for row counts, then join COLUMNS to detect timestamps.
            # region-us is the default; this can be parameterized later.
            query = f"""
                SELECT
                    ts.table_schema AS schemaname,
                    ts.table_name   AS tablename,
                    ts.total_rows   AS row_count,
                    (
                        SELECT COUNT(1)
                        FROM `{project}`.`region-us`.INFORMATION_SCHEMA.COLUMNS c
                        WHERE c.table_schema = ts.table_schema
                          AND c.table_name   = ts.table_name
                          AND LOWER(c.column_name) IN ('updated_at', 'created_at')
                    ) > 0           AS has_timestamps
                FROM `{project}`.`region-us`.INFORMATION_SCHEMA.TABLE_STORAGE ts
                WHERE ts.total_rows IS NOT NULL
                ORDER BY ts.total_rows DESC
                LIMIT 50
            """
            rows = client.query(query).result()
            return [
                {
                    "schemaname": r.schemaname,
                    "tablename": r.tablename,
                    "row_count": r.row_count or 0,
                    "has_timestamps": bool(r.has_timestamps),
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("Error connecting to BigQuery: %s", e)
            return []
