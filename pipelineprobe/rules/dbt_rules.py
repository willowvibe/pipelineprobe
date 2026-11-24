from typing import List

from pipelineprobe.models import DbtModel, Issue


def check_missing_tests(context: dict) -> List[Issue]:
    issues = []
    models: List[DbtModel] = context.get("dbt_models", [])
    for model in models:
        if model.tests_count == 0:
            issues.append(
                Issue(
                    severity="warning",
                    category="dbt",
                    summary=f"dbt model '{model.name}' has no tests.",
                    details="Models without tests can introduce silent data quality issues.",
                    recommendation="Add at least unique and not_null tests for primary keys.",
                    affected_resources=[model.name],
                )
            )
    return issues


def check_failing_models(context: dict) -> List[Issue]:
    issues = []
    models: List[DbtModel] = context.get("dbt_models", [])
    for model in models:
        if model.last_run_status in ("error", "fail"):
            issues.append(
                Issue(
                    severity="critical",
                    category="dbt",
                    summary=f"dbt model '{model.name}' failed in the last run.",
                    details=f"Last run status: {model.last_run_status}",
                    recommendation="Investigate and fix the failing model or tests.",
                    affected_resources=[model.name],
                )
            )
    return issues


def check_missing_descriptions(context: dict) -> List[Issue]:
    issues = []
    models: List[DbtModel] = context.get("dbt_models", [])
    for model in models:
        if not model.description.strip():
            issues.append(
                Issue(
                    severity="info",
                    category="dbt",
                    summary=f"dbt model '{model.name}' has no description.",
                    details=(
                        "Undocumented models are harder for new team members "
                        "and BI users to understand and trust."
                    ),
                    recommendation=(
                        "Add a description for the model in its schema YAML file."
                    ),
                    affected_resources=[model.name],
                )
            )
    return issues


def register_dbt_rules(engine):
    engine.register_rule(check_missing_tests)
    engine.register_rule(check_failing_models)
    engine.register_rule(check_missing_descriptions)
