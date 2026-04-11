import json
from datetime import timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from pipelineprobe.models import Issue


def _json_default(obj):
    """Fallback serializer for types not handled by the default JSON encoder."""
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class ReportRenderer:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def render_html(self, issues: list[Issue], summary: dict) -> Path:
        from datetime import datetime
        from pipelineprobe import __version__

        template = self.env.get_template("report.html")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Identify top 3 critical/warning actions sorted by severity then category
        top_actions = sorted(
            [i for i in issues if i.severity in ("critical", "warning")],
            key=lambda x: (x.severity == "warning", x.category),
        )[:3]

        # SVG ring offset: circumference = 2π × r(40) ≈ 251.3
        # offset = circumference × (1 − score/100) → 0 means full ring, 251.3 means empty
        _circ = 251.3
        score = summary.get("score", 0)
        ring_offset = round(_circ * (1 - score / 100), 2)

        html_content = template.render(
            issues=issues,
            summary=summary,
            generated_at=generated_at,
            version=__version__,
            top_actions=top_actions,
            metadata=summary.get("metadata", {}),
            ring_offset=ring_offset,
        )
        output_path = self.output_dir / "pipelineprobe-report.html"
        with open(output_path, "w") as f:
            f.write(html_content)
        return output_path

    def render_json(self, issues: list[Issue], summary: dict) -> Path:
        output_path = self.output_dir / "report.json"
        data = {"summary": summary, "issues": [i.model_dump() for i in issues]}
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=_json_default)
        return output_path
