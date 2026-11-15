"""Tests for the optional ``cloud`` extra (BigQuery / Snowflake SDKs)."""

import subprocess
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from pipelineprobe.cli import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_SDKS = ("google-cloud-bigquery", "snowflake-connector-python")
INSTALL_HINT = 'pip install "pipelineprobe[cloud]"'

runner = CliRunner()

BIGQUERY_CONFIG = """\
orchestrator:
  type: airflow
  base_url: "http://test"
dbt:
  project_dir: "./"
warehouse:
  type: bigquery
  project_id: "test-project"
report:
  format: "json"
  output_dir: "./reports"
"""

SNOWFLAKE_CONFIG = """\
orchestrator:
  type: airflow
  base_url: "http://test"
dbt:
  project_dir: "./"
warehouse:
  type: snowflake
  account: "acct"
  username: "user"
  password: "pw"
report:
  format: "json"
  output_dir: "./reports"
"""


def _output(result) -> str:
    """Return stdout plus stderr so the assertion works across typer versions."""
    return (result.output or "") + (getattr(result, "stderr", "") or "")


def _assert_clean_exit(result) -> None:
    """Exit 1 must come from typer.Exit, not from an uncaught crash."""
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), (
        f"expected SystemExit (typer.Exit), got {result.exception!r}"
    )
    output = _output(result)
    assert "Traceback" not in output
    assert "UnboundLocalError" not in output


def _block_cloud_sdk(monkeypatch, connector: str, sdk_module: str) -> None:
    """Simulate a base install by blocking a cloud SDK and its connector module."""
    # Another test module may already have imported the connector module, which
    # would let the CLI's lazy import succeed without touching the SDK.
    monkeypatch.delitem(
        sys.modules, f"pipelineprobe.connectors.{connector}", raising=False
    )

    parent_name, _, leaf = sdk_module.rpartition(".")
    parent = sys.modules.get(parent_name)
    if parent is not None:
        # `from google.cloud import bigquery` resolves a cached parent attribute
        # before consulting sys.modules, so detach it as well.
        monkeypatch.delattr(parent, leaf, raising=False)
    monkeypatch.setitem(sys.modules, sdk_module, None)


def test_cloud_sdks_are_declared_only_as_an_optional_extra():
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as fh:
        project = tomllib.load(fh)["project"]

    runtime_deps = project["dependencies"]
    for sdk in CLOUD_SDKS:
        assert not any(sdk in dep for dep in runtime_deps), (
            f"{sdk} must not be a runtime dependency"
        )

    cloud_extra = project["optional-dependencies"]["cloud"]
    for sdk in CLOUD_SDKS:
        assert any(sdk in dep for dep in cloud_extra), f"{sdk} missing from cloud extra"

    assert any("pytest" in dep for dep in project["optional-dependencies"]["dev"])


def test_audit_bigquery_without_cloud_extra_exits_with_hint(monkeypatch, tmp_path):
    _block_cloud_sdk(monkeypatch, "bigquery", "google.cloud.bigquery")
    config = tmp_path / "pipelineprobe.yml"
    config.write_text(BIGQUERY_CONFIG)

    with patch("pipelineprobe.cli.AirflowConnector") as airflow_cls:
        airflow_cls.return_value.get_dags.return_value = []
        result = runner.invoke(app, ["audit", "--config", str(config)])

    _assert_clean_exit(result)
    output = _output(result)
    assert INSTALL_HINT in output
    assert "BigQuery support requires the 'cloud' extra" in output


def test_audit_snowflake_without_cloud_extra_exits_with_hint(monkeypatch, tmp_path):
    _block_cloud_sdk(monkeypatch, "snowflake", "snowflake.connector")
    config = tmp_path / "pipelineprobe.yml"
    config.write_text(SNOWFLAKE_CONFIG)

    with patch("pipelineprobe.cli.AirflowConnector") as airflow_cls:
        airflow_cls.return_value.get_dags.return_value = []
        result = runner.invoke(app, ["audit", "--config", str(config)])

    _assert_clean_exit(result)
    output = _output(result)
    assert INSTALL_HINT in output
    assert "Snowflake support requires the 'cloud' extra" in output


def test_doctor_reports_missing_bigquery_sdk(monkeypatch, tmp_path):
    _block_cloud_sdk(monkeypatch, "bigquery", "google.cloud.bigquery")
    config = tmp_path / "pipelineprobe.yml"
    config.write_text(BIGQUERY_CONFIG)

    with patch("pipelineprobe.cli.httpx.Client") as client_cls:
        response = client_cls.return_value.__enter__.return_value.get.return_value
        response.json.return_value = {
            "metadatabase": {"status": "healthy"},
            "scheduler": {"status": "healthy"},
        }
        result = runner.invoke(app, ["doctor", "--config", str(config)])

    _assert_clean_exit(result)
    assert f'BigQuery: MISSING SDK — {INSTALL_HINT}' in _output(result)


BLOCKED_IMPORT_SCRIPT = """
import sys


class BlockCloudSDKs:
    _blocked = {"google.cloud.bigquery", "snowflake.connector"}

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self._blocked:
            raise ImportError(f"blocked for test: {fullname}")
        return None


sys.meta_path.insert(0, BlockCloudSDKs())

import pipelineprobe.cli  # noqa: E402,F401

assert "google.cloud.bigquery" not in sys.modules
assert "snowflake.connector" not in sys.modules
print("cli-imported-without-cloud-sdks")
"""


def test_cli_imports_without_cloud_sdks():
    result = subprocess.run(
        [sys.executable, "-c", BLOCKED_IMPORT_SCRIPT],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "cli-imported-without-cloud-sdks" in result.stdout
