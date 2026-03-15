from .engine import RuleEngine
from .airflow_rules import register_airflow_rules
from .dbt_rules import register_dbt_rules
from .postgres_rules import register_postgres_rules


def get_configured_engine() -> RuleEngine:
    engine = RuleEngine()
    register_airflow_rules(engine)
    register_dbt_rules(engine)
    register_postgres_rules(engine)
    return engine
