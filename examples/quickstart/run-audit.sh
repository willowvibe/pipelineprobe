#!/usr/bin/env bash
#
# PipelineProbe quickstart entrypoint.
#
#   1. Wait for Airflow's /health endpoint and for all eight demo DAGs.
#   2. Seed a deterministic run history through the Airflow REST API.
#   3. Run the audit against the quickstart config.
#
# Runs inside the pipelineprobe container (python:3.11-slim, no curl); the
# HTTP work is done with the Python standard library only.

set -euo pipefail

AIRFLOW_URL="${AIRFLOW_URL:-http://airflow:8080}"
AIRFLOW_USER="${AIRFLOW_USER:-admin}"
AIRFLOW_PASSWORD="${AIRFLOW_PASSWORD:-admin}"
PIPELINEPROBE_CONFIG="${PIPELINEPROBE_CONFIG:-/app/quickstart/pipelineprobe.yml}"
AIRFLOW_WAIT_TIMEOUT="${AIRFLOW_WAIT_TIMEOUT:-180}"
AIRFLOW_RUN_TIMEOUT="${AIRFLOW_RUN_TIMEOUT:-240}"

echo "==> Waiting for Airflow at ${AIRFLOW_URL} (timeout ${AIRFLOW_WAIT_TIMEOUT}s)..."
python3 - "$AIRFLOW_URL" "$AIRFLOW_USER" "$AIRFLOW_PASSWORD" "$AIRFLOW_WAIT_TIMEOUT" <<'PY'
"""Poll /health, then the DAG list, until every quickstart DAG is registered."""
import base64
import json
import sys
import time
import urllib.request

base_url = sys.argv[1].rstrip("/")
username, password = sys.argv[2], sys.argv[3]
timeout = float(sys.argv[4])

EXPECTED_DAGS = [
    "daily_sales_pipeline",
    "nightly_customer_sync",
    "healthy_pipeline_1",
    "healthy_pipeline_2",
    "healthy_pipeline_3",
    "healthy_pipeline_4",
    "healthy_pipeline_5",
    "healthy_pipeline_6",
]

credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
auth_headers = {
    "Authorization": f"Basic {credentials}",
    "Accept": "application/json",
}


def registered_dag_ids():
    """Return the DAG ids visible through the authenticated REST API."""
    request = urllib.request.Request(
        f"{base_url}/api/v1/dags?limit=100", headers=auth_headers
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.loads(response.read().decode())
    return {dag["dag_id"] for dag in body.get("dags", [])}


deadline = time.time() + timeout
last_progress = 0.0

while time.time() < deadline:
    # /health is unauthenticated and only returns 200 once the metadata DB and
    # scheduler look healthy.  Connection errors mean the container is starting.
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
    except Exception as exc:
        if time.time() - last_progress >= 10:
            print(f"    Airflow is not healthy yet ({exc}); retrying...", flush=True)
            last_progress = time.time()
        time.sleep(3)
        continue

    try:
        dag_ids = registered_dag_ids()
    except Exception as exc:
        if time.time() - last_progress >= 10:
            print(
                f"    Airflow is healthy but its API is not ready yet ({exc}); retrying...",
                flush=True,
            )
            last_progress = time.time()
        time.sleep(3)
        continue

    missing = [dag_id for dag_id in EXPECTED_DAGS if dag_id not in dag_ids]
    if not missing:
        print(
            f"    Airflow is healthy and all {len(EXPECTED_DAGS)} quickstart DAGs are registered.",
            flush=True,
        )
        raise SystemExit(0)

    if time.time() - last_progress >= 10:
        print(f"    Waiting for DAGs to be parsed: {', '.join(missing)}", flush=True)
        last_progress = time.time()
    time.sleep(3)

print(
    f"ERROR: timed out after {timeout:.0f}s waiting for Airflow at {base_url}.\n"
    "       Check `docker compose ps` and `docker compose logs airflow airflow-init`.\n"
    "       The eight quickstart DAGs must be mounted at /opt/airflow/dags and parsed\n"
    "       without import errors (see `docker compose exec airflow airflow dags list`).",
    file=sys.stderr,
)
raise SystemExit(1)
PY

echo "==> Seeding demo DAG runs (nightly has 6 runs, 2 of them fail)..."
python3 - "$AIRFLOW_URL" "$AIRFLOW_USER" "$AIRFLOW_PASSWORD" "$AIRFLOW_RUN_TIMEOUT" <<'PY'
"""Create the seeded DAG runs and wait for each one to reach a terminal state."""
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

base_url = sys.argv[1].rstrip("/")
username, password = sys.argv[2], sys.argv[3]
timeout = float(sys.argv[4])

# Every DAG needs at least one run (otherwise the stale-DAG rule fires for it).
# The nightly DAG gets six so its seeded 2/6 failure ratio exceeds the 20%
# high-failure-rate threshold.  seed_3 and seed_6 raise inside the task.
RUN_PLAN = {
    "daily_sales_pipeline": 1,
    "nightly_customer_sync": 6,
    "healthy_pipeline_1": 1,
    "healthy_pipeline_2": 1,
    "healthy_pipeline_3": 1,
    "healthy_pipeline_4": 1,
    "healthy_pipeline_5": 1,
    "healthy_pipeline_6": 1,
}

credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
headers = {
    "Authorization": f"Basic {credentials}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def request(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base_url + path, data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read().decode() or "{}")


# The DAGs are created unpaused; this only matters if a reused metadata
# database still holds a paused copy.  Un-pausing is idempotent.
for dag_id in RUN_PLAN:
    try:
        request("PATCH", f"/api/v1/dags/{dag_id}", {"is_paused": False})
    except Exception as exc:
        print(f"    WARNING: could not unpause {dag_id}: {exc}", file=sys.stderr)

now = datetime.now(timezone.utc).replace(microsecond=0)
seeded = []
for dag_id, run_count in RUN_PLAN.items():
    for index in range(1, run_count + 1):
        run_id = f"seed_{index}"
        # Distinct logical dates avoid the "DAG run already exists" conflict on
        # re-runs; 5-minute spacing keeps every run inside the 7-day window.
        logical_date = (
            now - timedelta(minutes=5 * (run_count - index + 1))
        ).isoformat()
        try:
            request(
                "POST",
                f"/api/v1/dags/{dag_id}/dagRuns",
                {"dag_run_id": run_id, "logical_date": logical_date, "conf": {}},
            )
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                raise
            print(f"    {dag_id}/{run_id} already exists; reusing it.", flush=True)
        seeded.append((dag_id, run_id))
    print(f"    queued {run_count} run(s) for {dag_id}", flush=True)

print("==> Waiting for seeded runs to finish...")
states = {}
pending = list(seeded)
deadline = time.time() + timeout
last_progress = 0.0

while pending and time.time() < deadline:
    still_pending = []
    for dag_id, run_id in pending:
        try:
            _, body = request("GET", f"/api/v1/dags/{dag_id}/dagRuns/{run_id}")
        except Exception as exc:
            print(
                f"    WARNING: could not read {dag_id}/{run_id}: {exc}",
                file=sys.stderr,
            )
            still_pending.append((dag_id, run_id))
            continue
        state = body.get("state", "unknown")
        if state in ("success", "failed"):
            states[(dag_id, run_id)] = state
        else:
            still_pending.append((dag_id, run_id))
    pending = still_pending
    if pending:
        if time.time() - last_progress >= 15:
            print(f"    {len(pending)} run(s) still in progress...", flush=True)
            last_progress = time.time()
        time.sleep(3)

if pending:
    details = ", ".join(f"{dag_id}/{run_id}" for dag_id, run_id in pending)
    print(
        f"ERROR: timed out after {timeout:.0f}s waiting for DAG runs: {details}\n"
        "       The Airflow scheduler may not be processing runs; check\n"
        "       `docker compose logs airflow` for task or scheduler errors.",
        file=sys.stderr,
    )
    raise SystemExit(1)

print(
    "    Run states: "
    + ", ".join(
        f"{dag_id}/{run_id}={states[(dag_id, run_id)]}"
        for dag_id, run_id in seeded
    ),
    flush=True,
)
failed = sorted(
    f"{dag_id}/{run_id}"
    for dag_id, run_id in seeded
    if states[(dag_id, run_id)] == "failed"
)
if failed != ["nightly_customer_sync/seed_3", "nightly_customer_sync/seed_6"]:
    print(
        "    WARNING: seeded failures differ from the expected "
        f"nightly seed_3/seed_6 pair (got: {', '.join(failed) or 'none'}).",
        file=sys.stderr,
    )
PY

echo "==> Running PipelineProbe audit..."
exec pipelineprobe audit --config "$PIPELINEPROBE_CONFIG" --format both
