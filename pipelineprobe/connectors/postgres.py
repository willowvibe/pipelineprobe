import logging
from typing import Any, Dict, List

import psycopg2
import psycopg2.extras

from pipelineprobe.config import WarehouseConfig

logger = logging.getLogger(__name__)


class PostgresConnector:
    def __init__(self, config: WarehouseConfig):
        self.config = config

    def get_stats_sync(self) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = psycopg2.connect(self.config.dsn)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        t.schemaname, 
                        t.relname AS tablename, 
                        t.n_live_tup AS row_count,
                        EXISTS (
                            SELECT 1 FROM information_schema.columns c 
                            WHERE c.table_schema = t.schemaname 
                              AND c.table_name = t.relname 
                              AND c.column_name IN ('updated_at', 'created_at')
                        ) AS has_timestamps
                    FROM pg_stat_user_tables t
                    ORDER BY t.n_live_tup DESC
                    LIMIT 50
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error("Error connecting to Postgres: %s", e)
            return []
        finally:
            if conn:
                conn.close()
