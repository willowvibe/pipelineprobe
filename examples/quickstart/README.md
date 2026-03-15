# PipelineProbe Quickstart

Run a full data pipeline audit in under 5 minutes using this example environment.

## What's inside?
- **Apache Airflow**: Pre-loaded with example DAGs.
- **Postgres**: Serving as both the Airflow backend and a sample warehouse.
- **PipelineProbe**: Automatically audits the stack and generates a report.

## Prerequisites
- Docker and Docker Compose installed.

## Run the Audit

1. **Start the environment**:
   ```bash
   docker compose up --build
   ```

2. **Wait for completion**:
   PipelineProbe will wait for Airflow to start, run the audit, and then exit.

3. **View the report**:
   Once the `pipelineprobe` container finished, check the generated report in:
   `./reports/pipelineprobe-report.html`

## How it works
The `docker-compose.yml` mounts this directory into the PipelineProbe container. It uses the pre-configured `pipelineprobe.yml` to connect to the internal Docker network services (`airflow:8080` and `postgres:5432`).
