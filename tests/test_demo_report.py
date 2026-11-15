"""Tests for the committed sample report and its build script."""

import importlib.util
import json
from collections import Counter
from pathlib import Path

from pipelineprobe.models import Issue
from pipelineprobe.renderer import ReportRenderer

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "site" / "demo" / "sample_audit.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_demo_report.py"


def _load_fixture():
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    issues = [Issue.model_validate(raw) for raw in data["issues"]]
    return data["summary"], issues


def _load_build_script():
    spec = importlib.util.spec_from_file_location("build_demo_report", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_matches_the_real_quickstart_audit():
    """Pin the fixture so the published demo cannot drift silently."""
    summary, issues = _load_fixture()

    counts = Counter(issue.severity for issue in issues)
    assert counts["critical"] == 2
    assert counts["warning"] == 5
    assert counts["info"] == 0
    assert len(issues) == 7
    assert summary["score"] == 30
    assert summary["critical_count"] == 2
    assert summary["warning_count"] == 5
    assert summary["info_count"] == 0
    assert summary["total_issues"] == 7
    assert summary["dag_count"] == 8
    assert summary["score_formula"]
    assert summary["metadata"]


def test_fixture_renders_through_report_renderer(tmp_path):
    summary, issues = _load_fixture()

    rendered = ReportRenderer(str(tmp_path)).render_html(issues, summary)
    html = rendered.read_text(encoding="utf-8")

    assert ">30<" in html
    assert "Health Score" in html
    assert "has a high failure rate" in html
    assert "PipelineProbe v0.3.0" in html


def test_build_report_labels_the_page_as_sample_data(tmp_path):
    build_demo_report = _load_build_script()
    output_path = tmp_path / "site" / "report" / "index.html"

    written = build_demo_report.build_report(
        fixture_path=FIXTURE_PATH, output_path=output_path
    )

    assert written == output_path
    html = output_path.read_text(encoding="utf-8")
    assert "Sample report" in html
    assert "synthetic data from the bundled quickstart stack" in html
    assert 'href="../"' in html
    assert html.index("<body>") < html.index("Sample report")
    # The renderer's own filename must not be left behind beside index.html.
    assert [p.name for p in output_path.parent.iterdir()] == ["index.html"]
