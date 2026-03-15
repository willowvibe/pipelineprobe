# CI/CD Integration

PipelineProbe is designed to run seamlessly in your continuous integration and deployment pipelines. By failing your build when regressions are identified, PipelineProbe acts as a quality gate for your data platform.

---

## GitHub Actions

We provide a ready-to-use workflow at [`examples/github_action.yml`](../examples/github_action.yml). The core audit step:

```yaml
      - name: Run PipelineProbe Audit
        env:
          PIPELINEPROBE_AIRFLOW_PASSWORD: ${{ secrets.AIRFLOW_PASSWORD }}
          PIPELINEPROBE_WAREHOUSE_DSN: ${{ secrets.WAREHOUSE_DSN }}
        run: |
          pipelineprobe audit \
            --config pipelineprobe.yml \
            --format both \
            --fail-on-critical 5
```

### Archive Reports

We strongly recommend uploading the generated reports so they are accessible per-run:

```yaml
      - name: Upload PipelineProbe Reports
        if: always()   # upload even if the audit step fails
        uses: actions/upload-artifact@v4
        with:
          name: pipelineprobe-reports
          path: reports/
          retention-days: 30
```

---

## GitLab CI

```yaml
pipelineprobe:audit:
  stage: audit
  image: python:3.11-slim
  variables:
    PIPELINEPROBE_AIRFLOW_PASSWORD: $AIRFLOW_PASSWORD
    PIPELINEPROBE_WAREHOUSE_DSN: $WAREHOUSE_DSN
  script:
    - pip install pipelineprobe
    - pipelineprobe audit --config pipelineprobe.yml --format both --fail-on-critical 5
  artifacts:
    when: always
    paths:
      - reports/
    expire_in: 30 days
```

---

## Authentication and Secrets

Always inject sensitive values via your CI provider's secret management — **never** commit credentials to source control.

| Environment Variable | Purpose |
|---|---|
| `PIPELINEPROBE_AIRFLOW_PASSWORD` | Airflow REST API password |
| `PIPELINEPROBE_WAREHOUSE_DSN` | PostgreSQL DSN |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to BigQuery service account JSON |

For BigQuery, mount the service account key as a CI secret file and set `GOOGLE_APPLICATION_CREDENTIALS` to the mounted path.

For Snowflake, set `warehouse.account`, `username`, and `password` in `pipelineprobe.yml` and inject the password via a custom env var that you reference in the YAML, or configure via a secrets manager.

---

## Failing the Build (`fail_on_critical`)

Configure PipelineProbe to return exit code `1` when critical issues exceed a threshold:

```yaml
report:
  fail_on_critical: 0   # fail if even 1 critical issue is found
```

- `0` = fail on **any** critical issue (strictest, ideal for greenfield projects)
- `5` = tolerate up to 5 critical issues (useful when onboarding to legacy stacks)

The threshold can also be overridden per-run without changing the config:

```bash
pipelineprobe audit --fail-on-critical 0
```

---

## Gradually Tightening Standards

A recommended adoption pattern for existing codebases:

1. Start with `fail_on_critical: 50` to ensure the CI job doesn't block your team immediately.
2. Each sprint, reduce the threshold by however many issues you fix.
3. Track progress by archiving `report.json` and comparing counts over time.

