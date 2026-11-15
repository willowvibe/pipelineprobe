FROM python:3.11-slim

WORKDIR /app

# Install the package (the build backend needs the package sources present).
COPY pyproject.toml README.md ./
COPY pipelineprobe/ ./pipelineprobe/
RUN pip install --no-cache-dir .

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["pipelineprobe"]
CMD ["--help"]
