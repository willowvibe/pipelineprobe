from typing import List, Dict, Any
import snowflake.connector
from pipelineprobe.config import WarehouseConfig

class SnowflakeConnector:
    def __init__(self, config: WarehouseConfig):
        self.config = config

    def get_stats_sync(self) -> List[Dict[str, Any]]:
        try:
            conn = snowflake.connector.connect(
                user=self.config.username if self.config.username else 'admin',
                password=self.config.password if self.config.password else '',
                account=self.config.account if self.config.account else '',
            )
            cursor = conn.cursor()
            query = """
                SELECT 
                    TABLE_SCHEMA as schemaname, 
                    TABLE_NAME as tablename, 
                    ROW_COUNT as row_count,
                    EXISTS (
                        SELECT 1 
                        FROM INFORMATION_SCHEMA.COLUMNS c 
                        WHERE c.TABLE_SCHEMA = t.TABLE_SCHEMA 
                          AND c.TABLE_NAME = t.TABLE_NAME 
                          AND c.COLUMN_NAME IN ('UPDATED_AT', 'CREATED_AT')
                    ) as has_timestamps
                FROM INFORMATION_SCHEMA.TABLES t
                WHERE TABLE_SCHEMA != 'INFORMATION_SCHEMA'
                  AND ROW_COUNT IS NOT NULL
                ORDER BY ROW_COUNT DESC
                LIMIT 50;
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            result = []
            for r in rows:
                result.append({
                    "schemaname": r[0],
                    "tablename": r[1],
                    "row_count": r[2] or 0,
                    "has_timestamps": bool(r[3])
                })
            
            cursor.close()
            conn.close()
            return result
        except Exception as e:
            print(f"Error connecting to Snowflake: {e}")
            return []
