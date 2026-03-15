from pipelineprobe.config import load_config, PipelineProbeConfig


def test_load_config_defaults(tmp_path):
    # Pass a path that doesn't exist to test defaults
    dummy_path = tmp_path / "nonexistent.yml"
    config = load_config(str(dummy_path))

    assert isinstance(config, PipelineProbeConfig)
    assert config.orchestrator.type == "airflow"
    assert config.dbt.target == "prod"
    assert config.warehouse.type == "postgres"
    assert config.report.format == "html"
