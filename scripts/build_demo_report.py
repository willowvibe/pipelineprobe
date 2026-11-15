#!/usr/bin/env python3
"""Build the static sample report published on the PipelineProbe site.

Reads the committed fixture at ``site/demo/sample_audit.json`` (an unmodified
JSON report produced by auditing the bundled quickstart stack), renders it
through the same ``ReportRenderer`` the CLI uses, and writes a single
self-contained page to ``site/report/index.html``.  The page is labelled as
sample data with a banner so it is never mistaken for client work.

Usage:
    uv run --project . python scripts/build_demo_report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Allow running the script directly from any working directory.
    sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError  # noqa: E402

from pipelineprobe.models import Issue  # noqa: E402
from pipelineprobe.renderer import ReportRenderer  # noqa: E402

FIXTURE_PATH = REPO_ROOT / "site" / "demo" / "sample_audit.json"
OUTPUT_PATH = REPO_ROOT / "site" / "report" / "index.html"

REQUIRED_SUMMARY_KEYS = (
    "score",
    "critical_count",
    "warning_count",
    "info_count",
    "total_issues",
    "dag_count",
)

SAMPLE_BANNER = """
    <div style="background:#0f172a;color:#f8fafc;border-bottom:3px solid #f59e0b;
                padding:14px 20px;text-align:center;line-height:1.5;
                font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                font-size:14px;">
        <strong>Sample report</strong> &mdash; synthetic data from the bundled quickstart stack.
        <a href="../" style="color:#fbbf24;text-decoration:underline;">Back to PipelineProbe</a>
    </div>
"""


def load_fixture(path: Path) -> tuple[list[Issue], dict]:
    """Load and validate the sample audit fixture.

    Raises ``SystemExit`` with a clear message when the fixture is missing or
    malformed so the build fails loudly instead of publishing a broken page.
    """
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"error: sample fixture not found at {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: could not read sample fixture {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"error: sample fixture {path} must contain a JSON object")

    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise SystemExit(f"error: sample fixture {path} is missing a 'summary' object")

    missing = [key for key in REQUIRED_SUMMARY_KEYS if key not in summary]
    if missing:
        raise SystemExit(
            f"error: sample fixture {path} summary is missing required keys: "
            + ", ".join(missing)
        )

    raw_issues = data.get("issues")
    if not isinstance(raw_issues, list):
        raise SystemExit(f"error: sample fixture {path} is missing an 'issues' list")

    issues: list[Issue] = []
    for index, raw_issue in enumerate(raw_issues):
        if not isinstance(raw_issue, dict):
            raise SystemExit(
                f"error: sample fixture {path} issue #{index} must be a JSON object"
            )
        try:
            issues.append(Issue.model_validate(raw_issue))
        except ValidationError as exc:
            raise SystemExit(
                f"error: sample fixture {path} issue #{index} is not a valid Issue: {exc}"
            ) from exc

    return issues, summary


def inject_sample_banner(html: str) -> str:
    """Insert the sample-data banner immediately after the opening body tag."""
    marker = "<body>"
    if marker not in html:
        raise SystemExit("error: rendered report has no <body> tag to attach the banner to")
    return html.replace(marker, marker + SAMPLE_BANNER, 1)


def render_sample_report(issues: list[Issue], summary: dict, output_path: Path) -> Path:
    """Render validated issues through ``ReportRenderer`` and write ``output_path``."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ReportRenderer always writes pipelineprobe-report.html into its directory.
    rendered_path = ReportRenderer(str(output_path.parent)).render_html(issues, summary)
    html = rendered_path.read_text(encoding="utf-8")
    if rendered_path != output_path:
        rendered_path.unlink()

    output_path.write_text(inject_sample_banner(html), encoding="utf-8")
    return output_path


def build_report(fixture_path: Path = FIXTURE_PATH, output_path: Path = OUTPUT_PATH) -> Path:
    """Load the fixture, render it, and write ``output_path``."""
    issues, summary = load_fixture(fixture_path)
    return render_sample_report(issues, summary, output_path)


def main() -> None:
    issues, summary = load_fixture(FIXTURE_PATH)
    output_path = render_sample_report(issues, summary, OUTPUT_PATH)
    print(f"Wrote {output_path} (score {summary['score']})")


if __name__ == "__main__":
    main()
