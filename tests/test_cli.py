import os
import tempfile

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


# Note: A full test of the `audit` command requires mocking internal connectors,
# which will be added as we complete Phase 1 implementations.
