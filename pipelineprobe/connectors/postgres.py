import asyncpg
import asyncio
from typing import List, Dict, Any
from pipelineprobe.config import WarehouseConfig

class PostgresConnector:
    def __init__(self, config: WarehouseConfig):
        self.config = config

    async def get_table_stats(self) -> List[Dict[str, Any]]:
        try:
            conn = await asyncpg.connect(self.config.dsn)
            query = """
                SELECT 
                    t.schemaname, 
                    t.relname as tablename, 
                    t.n_live_tup as row_count,
                    EXISTS (
                        SELECT 1 
                        FROM information_schema.columns c 
                        WHERE c.table_schema = t.schemaname 
                          AND c.table_name = t.relname 
                          AND c.column_name IN ('updated_at', 'created_at')
                    ) as has_timestamps
                FROM pg_stat_user_tables t
                ORDER BY t.n_live_tup DESC
                LIMIT 50;
            """
            rows = await conn.fetch(query)
            await conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error connecting to Postgres: {e}")
            return []
            
    def get_stats_sync(self) -> List[Dict[str, Any]]:
        return asyncio.run(self.get_table_stats())
