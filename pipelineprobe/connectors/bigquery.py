import logging
from typing import Any, Dict, List, Optional

from google.cloud import bigquery

from pipelineprobe.config import WarehouseConfig

logger = logging.getLogger(__name__)

# JOBS_BY_PROJECT is only available in the US multi-region by default.
# Teams using a different home region should set warehouse.bq_region in config.
_DEFAULT_BQ_REGION = "region-us"


class BigQueryConnector:
    def __init__(self, config: WarehouseConfig):
        self.config = config
        self._bq_region: str = getattr(config, "bq_region", None) or _DEFAULT_BQ_REGION

    def _make_client(self) -> bigquery.Client:
        return (
            bigquery.Client(project=self.config.project_id)
            if self.config.project_id
            else bigquery.Client()
        )

    def get_stats_sync(self) -> List[Dict[str, Any]]:
        try:
            client = self._make_client()
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

    def get_cost_insights_sync(self) -> List[Dict[str, Any]]:
        """Return the top tables/queries by bytes billed over the past 30 days.

        Queries ``INFORMATION_SCHEMA.JOBS_BY_PROJECT`` which is available in all
        projects without extra setup.  Results are aggregated by *referenced table*
        so the output surfaces the costliest tables rather than individual queries.

        Returns a list of dicts with keys:
            table_id          str   — ``project.dataset.table``
            total_bytes_billed int  — cumulative bytes billed
            total_gb_billed   float — convenience alias in GiB
            query_count       int   — number of distinct queries that touched this table
        """
        try:
            client = self._make_client()
            project = client.project
            region = self._bq_region

            query = f"""
                SELECT
                    CONCAT(
                        ref.projectId, '.', ref.datasetId, '.', ref.tableId
                    ) AS table_id,
                    SUM(j.total_bytes_billed)  AS total_bytes_billed,
                    COUNT(DISTINCT j.job_id)   AS query_count
                FROM
                    `{project}`.`{region}`.INFORMATION_SCHEMA.JOBS_BY_PROJECT j,
                    UNNEST(j.referenced_tables) AS ref
                WHERE
                    j.creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
                    AND j.job_type = 'QUERY'
                    AND j.state    = 'DONE'
                    AND j.error_result IS NULL
                    AND j.total_bytes_billed > 0
                GROUP BY table_id
                ORDER BY total_bytes_billed DESC
                LIMIT 25
            """
            rows = client.query(query).result()
            results = []
            for r in rows:
                billed = int(r.total_bytes_billed or 0)
                results.append(
                    {
                        "table_id": r.table_id,
                        "total_bytes_billed": billed,
                        "total_gb_billed": round(billed / (1024 ** 3), 2),
                        "query_count": int(r.query_count or 0),
                    }
                )
            return results
        except Exception as e:
            logger.error("Error fetching BigQuery cost insights: %s", e)
            return []
