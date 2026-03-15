from typing import List, Dict, Any
from google.cloud import bigquery
from pipelineprobe.config import WarehouseConfig

class BigQueryConnector:
    def __init__(self, config: WarehouseConfig):
        self.config = config

    def get_stats_sync(self) -> List[Dict[str, Any]]:
        try:
            # Default to auto-discovery from GOOGLE_APPLICATION_CREDENTIALS
            # or explicit project if provided in config
            client = bigquery.Client(project=self.config.project_id) if self.config.project_id else bigquery.Client()
            
            # Generic query aggregating across region-us. 
            # In a real tool, the region might need to be parameterized.
            query = """
                SELECT 
                    table_schema as schemaname, 
                    table_name as tablename, 
                    total_rows as row_count,
                    true as has_timestamps
                FROM 
                    `region-us`.INFORMATION_SCHEMA.TABLE_STORAGE
                ORDER BY total_rows DESC
                LIMIT 50;
            """
            query_job = client.query(query)
            rows = query_job.result()
            
            return [
                {
                    "schemaname": r.schemaname,
                    "tablename": r.tablename,
                    "row_count": r.row_count,
                    "has_timestamps": r.has_timestamps
                }
                for r in rows
            ]
        except Exception as e:
            print(f"Error connecting to BigQuery: {e}")
            return []
