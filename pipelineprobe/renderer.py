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
        template = self.env.get_template("report.html")
        html_content = template.render(issues=issues, summary=summary)
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
