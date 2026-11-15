"""Tests for the static landing page in site/index.html."""

from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPO_ROOT / "site" / "index.html"

PAGES_VIDEO = "assets/pipelineprobe-demo.mp4"
RELEASE_VIDEO = (
    "https://github.com/willowvibe/pipelineprobe/releases/download/v0.3.0/"
    "pipelineprobe-demo.mp4"
)
RELEASE_TAG = "https://github.com/willowvibe/pipelineprobe/releases/tag/v0.3.0"
SAMPLE_DISCLAIMER = (
    "synthetic data from the bundled quickstart stack, not client work"
)


class _LandingPage(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.videos: list[dict[str, str]] = []
        self.sources: list[dict[str, str]] = []
        self.anchors: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): (value or "") for name, value in attrs}
        if tag == "video":
            self.videos.append(attributes)
        elif tag == "source":
            self.sources.append(attributes)
        elif tag == "a":
            self.anchors.append(attributes)


def _parse() -> _LandingPage:
    page = _LandingPage()
    page.feed(INDEX_PATH.read_text(encoding="utf-8"))
    page.close()
    return page


def test_video_has_required_player_attributes():
    videos = _parse().videos

    assert len(videos) == 1
    video = videos[0]
    for attribute in ("autoplay", "muted", "playsinline", "controls"):
        assert attribute in video
    assert video["preload"] == "auto"
    assert video["poster"] == "assets/poster.jpg"


def test_video_sources_prefer_the_pages_copy_then_the_release_asset():
    sources = [source.get("src") for source in _parse().sources]

    assert sources == [PAGES_VIDEO, RELEASE_VIDEO]


def test_report_and_release_links_are_relative_and_present():
    hrefs = [anchor.get("href", "") for anchor in _parse().anchors]

    assert "report/" in hrefs
    assert "/report/" not in hrefs
    assert RELEASE_TAG in hrefs


def test_sample_data_disclaimer_appears_near_the_report_and_video():
    html = INDEX_PATH.read_text(encoding="utf-8")

    assert html.count(SAMPLE_DISCLAIMER) >= 2
    assert "Sample data" in html
    assert html.index(SAMPLE_DISCLAIMER, html.index('id="demo-video"')) > html.index(
        'id="demo-video"'
    )


def test_three_proof_bullets_link_to_the_sample_report():
    anchors = {
        anchor["id"]: anchor.get("href")
        for anchor in _parse().anchors
        if anchor.get("id")
    }

    for anchor_id in ("proof-score", "proof-actions", "proof-filter"):
        assert anchors.get(anchor_id) == "report/"
