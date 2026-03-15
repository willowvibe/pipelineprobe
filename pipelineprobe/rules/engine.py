import logging
from typing import List, Callable, Any

from pipelineprobe.models import Issue

logger = logging.getLogger(__name__)


class RuleEngine:
    def __init__(self):
        self.rules: List[Callable[[Any], List[Issue]]] = []

    def register_rule(self, rule_func: Callable[[Any], List[Issue]]):
        self.rules.append(rule_func)

    def run(self, context: dict) -> List[Issue]:
        issues = []
        for rule in self.rules:
            try:
                result = rule(context)
                if result:
                    issues.extend(result)
            except Exception as e:
                logger.error("Error running rule %s: %s", rule.__name__, e)
        return issues
