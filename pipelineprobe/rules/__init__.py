from .engine import RuleEngine
from .airflow_rules import register_airflow_rules
from .dbt_rules import register_dbt_rules
from .postgres_rules import register_postgres_rules
from .cost_rules import register_cost_rules


def get_configured_engine() -> RuleEngine:
    engine = RuleEngine()
    # Orchestrator rules — apply to Airflow, Prefect, and Dagster data
    # (all three connectors populate the same "airflow_dags" / "airflow_tasks"
    # context keys via shared Dag / Task models).
    register_airflow_rules(engine)
    register_dbt_rules(engine)
    register_postgres_rules(engine)
    # Cost-insight rules — no-ops unless the matching warehouse type is active
    # and include_cost_section=true was set in the config.
    register_cost_rules(engine)
    return engine
