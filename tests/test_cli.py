import os
import tempfile
from unittest.mock import patch
from typer.testing import CliRunner
from pipelineprobe.cli import app

runner = CliRunner()


def test_cli_init():
    # Run in a temp dir to avoid conflict if pipelineprobe.yml already exists in project root
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0, result.stdout
            assert "Initialized pipelineprobe.yml" in result.stdout
            assert os.path.exists("pipelineprobe.yml"), "pipelineprobe.yml was not created"
        finally:
            os.chdir(old_cwd)


def test_cli_audit_help():
    result = runner.invoke(app, ["audit", "--help"])
    assert result.exit_code == 0
    assert "Run the PipelineProbe audit and generate a report" in result.stdout




def test_cli_audit_full():
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Create a valid config file
            with open("pipelineprobe.yml", "w") as f:
                f.write('''
orchestrator:
  base_url: "http://test"
  username: "a"
dbt:
  project_dir: "./"
warehouse:
  type: postgres
  dsn: "postgresql://test"
report:
  output_dir: "./reports"
  format: "html"
''')
            
            with patch("pipelineprobe.cli.AirflowConnector") as mock_airflow_cls, \
                 patch("pipelineprobe.cli.DbtConnector") as mock_dbt_cls, \
                 patch("pipelineprobe.cli.PostgresConnector") as mock_pg_cls, \
                 patch("pipelineprobe.cli.ReportRenderer") as mock_renderer_cls:
                 
                mock_airflow = mock_airflow_cls.return_value
                mock_airflow.get_dags.return_value = []
                
                mock_dbt = mock_dbt_cls.return_value
                mock_dbt.get_models.return_value = []
                
                mock_pg = mock_pg_cls.return_value
                mock_pg.get_stats_sync.return_value = []

                result = runner.invoke(app, ["audit", "--format", "json", "--fail-on-critical", "0"])
                
                assert result.exit_code == 0
                assert "Audit completed successfully" in result.stdout
                
                # Check arguments were parsed and overrode config
                mock_renderer_cls.return_value.render_json.assert_called_once()
        finally:
            os.chdir(old_cwd)

def test_cli_audit_invalid_format():
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            with open("pipelineprobe.yml", "w") as f:
                f.write('warehouse:\n  type: postgres\n  dsn: ""\nreport:\n  format: html')
                
            result = runner.invoke(app, ["audit", "--format", "csv"])
            assert result.exit_code != 0
            assert "Must be one of: both, html, json" in result.stdout or "validation error" in result.stdout
        finally:
            os.chdir(old_cwd)
