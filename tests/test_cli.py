from typer.testing import CliRunner
from pipelineprobe.cli import app

runner = CliRunner()

def test_cli_init():
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Initialized pipelineprobe.yml" in result.stdout

def test_cli_audit_help():
    result = runner.invoke(app, ["audit", "--help"])
    assert result.exit_code == 0
    assert "Run the PipelineProbe audit and generate a report" in result.stdout

# Note: A full test of the `audit` command requires mocking internal connectors, 
# which will be added as we complete Phase 1 implementations.
