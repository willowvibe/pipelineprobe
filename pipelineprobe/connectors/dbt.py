import json
import logging
from pathlib import Path
from typing import List

from pipelineprobe.config import DbtConfig
from pipelineprobe.models import DbtModel

logger = logging.getLogger(__name__)


class DbtConnector:
    def __init__(self, config: DbtConfig):
        self.config = config

    def get_models(self) -> List[DbtModel]:
        manifest_path = Path(self.config.manifest_path)
        run_results_path = Path(self.config.run_results_path)

        if not manifest_path.exists():
            logger.warning(
                "dbt manifest not found at %s — skipping dbt checks.", manifest_path
            )
            return []

        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error("Error reading manifest: %s", e)
            return []

        run_results = {}
        if run_results_path.exists():
            try:
                with open(run_results_path, "r") as f:
                    rr = json.load(f)
                    for res in rr.get("results", []):
                        run_results[res.get("unique_id")] = res.get("status", "unknown")
            except Exception as e:
                logger.error("Error reading run_results: %s", e)

        models = []
        nodes = manifest.get("nodes", {})
        tests_count = self._count_tests_per_model(manifest)

        for unique_id, node in nodes.items():
            if node.get("resource_type") == "model":
                models.append(
                    DbtModel(
                        name=node.get("name", "unknown"),
                        tests_count=tests_count.get(unique_id, 0),
                        last_run_status=run_results.get(unique_id, "unknown"),
                        tags=node.get("tags", []),
                    )
                )
        return models

    def _count_tests_per_model(self, manifest: dict) -> dict:
        tests = {}
        nodes = manifest.get("nodes", {})
        for unique_id, node in nodes.items():
            if node.get("resource_type") == "test":
                depends_on = node.get("depends_on", {}).get("nodes", [])
                for dep in depends_on:
                    if dep.startswith("model."):
                        tests[dep] = tests.get(dep, 0) + 1
        return tests
