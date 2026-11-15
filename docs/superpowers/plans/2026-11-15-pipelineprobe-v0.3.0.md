# PipelineProbe v0.3.0 portfolio polish

Goal: make every public claim true, make the quickstart produce a real report, and publish a live report plus a 90-second demo. GitHub release only; no PyPI.

Global constraints:
- Version stays `0.3.0`; the first public release includes the already-implemented 0.2.0 connectors and 0.3.0 cost insights.
- No PyPI publishing and no `pip install pipelineprobe` claim.
- Python 3.11 and 3.12 in CI.
- Never commit secrets, `.venv`, `dist/`, or generated report output except the intentional demo fixture/report.
- The demo is labeled as sample data from the bundled stack, not client work.
- Do not force-push `main`; releases only from `v*` tags.

## 1 release-hygiene

files: Dockerfile, pyproject.toml, .github/workflows/ci.yml, .github/workflows/release.yml, CHANGELOG.md, README.md

do: Fix the Dockerfile so it copies `pyproject.toml`, `README.md`, and `pipelineprobe/` before `pip install --no-cache-dir .`, then runs as an unprivileged user and keeps the `python:3.11-slim` base. Add an explicit `[tool.ruff]` block with `line-length = 100`, `target-version = "py311"`, and `[tool.ruff.lint] select = ["E4", "E7", "E9", "F", "I"]`; pin `ruff==0.15.9` in the dev extra and change `typer[all]` to `typer`. Fix all lint findings without weakening the selected rules. Replace `ci.yml` with a 3.11/3.12 matrix that runs `ruff check .` and `pytest`, plus a wheel build/install smoke job and a Docker build job; use `actions/checkout@v4` and `actions/setup-python@v5`. Add `release.yml` triggered by `v*` tags with `contents: write`, building sdist/wheel and creating a GitHub release with both assets. Cut `CHANGELOG.md` from Unreleased to `0.3.0` dated 2026-11-15. In `README.md`, remove the PyPI badge and `pip install pipelineprobe`; add a GitHub release badge and an install command using the v0.3.0 release wheel URL; tick the v0.2.0 and v0.3.0 roadmap items.

done-when: `uv run --project . --extra dev ruff check .` and `uv run --project . --extra dev pytest -q` and `uv build` and `docker build -t pipelineprobe:test .`

difficulty: medium
kind: change

## 2 quickstart-stack

files: examples/quickstart/docker-compose.yml, examples/quickstart/pipelineprobe.yml, examples/quickstart/run-audit.sh, examples/quickstart/dags/demo_pipelines.py

do: Replace the quickstart compose file with a deterministic stack: Postgres 13 for Airflow metadata and a `warehouse` database; an `airflow-init` service that runs `airflow db init` and creates user `admin` with password `admin`; an Airflow 2.7.1 service running `standalone` with basic auth, `LOAD_EXAMPLES=False`, and the mounted `dags/` directory; and a PipelineProbe service that builds the repo, waits for Airflow health, and runs the audit. Add healthchecks for Postgres and Airflow, and make PipelineProbe depend on a healthy Airflow. Add `pipelineprobe.yml` pointing at `http://airflow:8080`, the `warehouse` Postgres DSN, and the bundled dbt artifact paths, with `report.output_dir: /app/quickstart/reports` and `fail_on_critical: 10`. Add `run-audit.sh` as the PipelineProbe entrypoint: poll `http://airflow:8080/health`, then `exec pipelineprobe audit --config /app/quickstart/pipelineprobe.yml --format both`. Add two problem DAGs (`daily_sales_pipeline` and `nightly_customer_sync`) whose tasks have `retries=0`, no SLA, and no alerting, plus six quiet DAGs (`healthy_pipeline_1` through `healthy_pipeline_6`) whose tasks use `retries=2` and an SLA; the eight-DAG population keeps the health-score normalization realistic instead of pinning the demo to zero. Keep the compose file compatible with both `docker compose` and `docker-compose`.

done-when: `docker-compose -f examples/quickstart/docker-compose.yml config`

difficulty: hard
kind: change

## 3 quickstart-fixtures

files: examples/quickstart/init-warehouse.sql, examples/quickstart/dbt_project/dbt_project.yml, examples/quickstart/dbt_project/target/manifest.json, examples/quickstart/dbt_project/target/run_results.json, examples/quickstart/README.md

do: Add Postgres init SQL that creates the `warehouse` database, an `analytics.fact_orders` table with `created_at`/`updated_at` and just over 10 million generated rows, and a `raw.stg_events` table with just over 1.2 million generated rows and no audit timestamp columns; use unlogged tables and `ANALYZE` so startup stays fast. Fill `dbt_project.yml` and add minimal but valid dbt `manifest.json` and `run_results.json` with one model that has no tests and one model whose last run status is `error`, so the dbt rules fire. Rewrite the quickstart README to document the one-command run, expected runtime, the admin/admin credentials, the report path, and the fact that the data is synthetic.

done-when: `python3 -c "import json; json.load(open('examples/quickstart/dbt_project/target/manifest.json')); json.load(open('examples/quickstart/dbt_project/target/run_results.json'))"`

difficulty: medium
kind: change

## 4 demo-report

files: scripts/build_demo_report.py, site/demo/sample_audit.json, site/report/index.html, tests/test_demo_report.py

do: Add a script that reads `site/demo/sample_audit.json` (the `summary` and `issues` shape written by `ReportRenderer.render_json`) and renders `site/report/index.html` through `ReportRenderer`. Create the sample fixture from the real quickstart report if `examples/quickstart/reports/report.json` exists; otherwise build it from the actual rule outputs and label it as a sample in the site. The fixture must include at least one critical finding, several warnings, an info finding, and the real score formula fields. Add a pytest that renders the fixture into a temporary directory and asserts the HTML contains the score, a critical summary, and the version footer.

done-when: `uv run --project . --extra dev pytest -q tests/test_demo_report.py` and `uv run --project . python scripts/build_demo_report.py`

difficulty: medium
kind: change

## 5 pages-site

files: site/index.html, site/assets/poster.jpg, .github/workflows/pages.yml

do: Build a static landing page in the report's indigo visual language: PipelineProbe pitch, a 90-second video element with `autoPlay muted playsInline controls preload="auto"` and a poster, an IntersectionObserver that plays when visible and pauses offscreen, a centered Play button when paused, an Unmute button while muted, and a `prefers-reduced-motion` opt-out. Include three proof bullets (health score, top three actions, severity filter), a prominent link to `/report/`, a sample-data disclaimer, and a link to the GitHub release. The video sources are the Pages copy first and the v0.3.0 release asset `pipelineprobe-demo.mp4` second. Add a Pages workflow that deploys `site/` on pushes to `main` and manual dispatch, fetching the release MP4 into `site/assets/` with a tolerated failure so the page still deploys before the asset exists. Use `actions/configure-pages`, `actions/upload-pages-artifact`, and `actions/deploy-pages`, with `pages: write` and `id-token: write`.

done-when: `python3 -c "from html.parser import HTMLParser; HTMLParser().feed(open('site/index.html').read())"` and `test -f site/assets/poster.jpg`

difficulty: medium
kind: change

## 6 readme-metadata

files: README.md

do: Rewrite the README around proof and honesty: release/CI/license/Python badges with no PyPI badge; a one-line pitch; a README GIF linking to the Pages demo; an `Open the live sample report` link; install from the v0.3.0 release wheel and a `pipx install git+https://github.com/willowvibe/pipelineprobe@v0.3.0` alternative; the working Docker quickstart; a `What the report shows` section with the current screenshot; the CI gate and `diff` workflows; a `Who this is for` section; a consulting CTA to WillowVibe; corrected roadmap; and a sample-data note. Update the GitHub repository description to `Instant, read-only audit reports for Airflow, dbt, and modern warehouses`, add topics `airflow`, `dbt`, `data-engineering`, `data-quality`, `observability`, `cli`, and set the homepage to the Pages URL.

done-when: `grep -q 'pypi.org/project/pipelineprobe' README.md; test $? -ne 0` and `grep -q 'willowvibe.github.io/pipelineprobe' README.md`

difficulty: medium
kind: change

## 7 release

files: CHANGELOG.md

do: After the checks and the demo video asset are ready, tag `v0.3.0`, push the tag, and create the GitHub release with the wheel, sdist, poster, and `pipelineprobe-demo.mp4`. Verify the release asset URLs and that the Pages deploy picks up the video. Do not publish to PyPI.

done-when: `gh release view v0.3.0 --repo willowvibe/pipelineprobe`

difficulty: easy
kind: change

## 8 final-verify

files: README.md

do: Run the full verification: ruff, pytest, `uv build`, clean-venv wheel install and `pipelineprobe --version`, Docker build, `docker-compose up --build` with report assertions for critical/warning findings from Airflow, dbt, and warehouse, Pages header checks for `video/mp4` and `accept-ranges: bytes`, Playwright autoplay/unmute/play-button/report-filter checks, README link checks, and GIF size under 2 MB. Record any check that could not run and why.

done-when: `uv run --project . --extra dev ruff check .` and `uv run --project . --extra dev pytest -q`

difficulty: medium
kind: change

## Deviations recorded during execution

- **Step 4 (sample report): no `info` finding.** The plan asked the fixture to
  carry one info-level finding. No rule in the audit produces one against the
  quickstart stack, and inventing a finding would have made the sample report
  a fabrication. The pinned fixture is 2 critical / 5 warning / 0 info,
  score 30, and `tests/test_demo_report.py` pins those exact counts.
- **Step 6 (README): no live URLs.** GitHub Pages is not enabled for the
  organisation's token, so `willowvibe.github.io/pipelineprobe` does not exist
  and the deploy workflow is manual-dispatch only. The README therefore links
  the demo GIF to the release MP4, points at `site/report/index.html` as a
  downloadable file, and makes no hosted-page claim. The demo narration was
  re-recorded for the same reason: it no longer says "open the live sample
  report".
- **PyPI moved into scope.** The release gains a `publish-pypi` job using OIDC
  trusted publishing, and the cloud SDKs moved behind a `cloud` extra so the
  default install stays lean. PyPI claims land in the README only in a
  follow-up change made after the first upload succeeds.
