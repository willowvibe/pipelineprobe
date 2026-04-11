# CI/CD Integration

PipelineProbe is designed to run seamlessly in your continuous integration pipelines. By failing a build when regressions are detected, it acts as an automated quality gate for your data platform.

---

## GitHub Actions

A ready-to-use workflow is available at [`examples/github-actions/pipelineprobe.yml`](../examples/github-actions/pipelineprobe.yml). The core audit step:

```yaml
      - name: Install PipelineProbe
        run: pip install pipelineprobe

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

### Uploading Reports as Artifacts

Always upload the generated reports so they are accessible per run:

```yaml
      - name: Upload PipelineProbe Reports
        if: always()   # upload even if the audit step fails
        uses: actions/upload-artifact@v4
        with:
          name: pipelineprobe-reports
          path: reports/
          retention-days: 30
```

### Regression Detection with `diff`

Track quality trends by comparing the current report against a stored baseline:

```yaml
      - name: Download baseline report
        uses: actions/download-artifact@v4
        with:
          name: pipelineprobe-baseline
          path: baseline/

      - name: Run Audit
        run: pipelineprobe audit --format json

      - name: Diff against baseline
        run: pipelineprobe diff baseline/report.json reports/report.json

      - name: Promote current report to baseline
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: pipelineprobe-baseline
          path: reports/report.json
```

`pipelineprobe diff` exits with code `1` if any new issues appear in the current report, making regressions immediately visible in CI.

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
| `PIPELINEPROBE_WAREHOUSE_DSN` | PostgreSQL connection DSN |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to BigQuery service account JSON key |

**BigQuery** — Mount the service account key as a CI secret file and set `GOOGLE_APPLICATION_CREDENTIALS` to its path.

**Snowflake** — Set `warehouse.account` and `username` in the YAML; inject the password via a CI secret or a secrets manager reference. Do not store the password in the YAML file.

---

## `fail_on_critical` — Build Quality Gate

Configure PipelineProbe to return exit code `1` when critical issues exceed a threshold:

```yaml
# pipelineprobe.yml
report:
  fail_on_critical: 0   # fail if even 1 critical issue is found
```

Or override per run without editing the config file:

```bash
pipelineprobe audit --fail-on-critical 0
```

### Threshold guide

| Setting | When to use |
|---|---|
| `0` | Greenfield or high-standards teams — fail on any critical issue |
| `5` | Onboarding to a legacy stack — tolerate a small backlog while teams address issues |
| `50` | Initial adoption — capture a baseline without blocking CI immediately |

---

## Gradually Tightening Standards

A recommended adoption pattern:

1. Start with `fail_on_critical: 50` to avoid blocking the team on day one.
2. Each sprint, reduce the threshold by the number of issues your team resolved.
3. Archive `report.json` each run and use `pipelineprobe diff` to track progress.
4. Aim for `fail_on_critical: 0` as the long-term standard.

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Audit succeeded; critical count at or below threshold |
| `1` | Critical count exceeds threshold, or a config / connectivity error |

The `diff` command follows the same convention:

| Code | Meaning |
|---|---|
| `0` | No regressions detected between the two reports |
| `1` | One or more new issues appeared in the current report |
