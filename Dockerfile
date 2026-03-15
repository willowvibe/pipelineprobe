FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any needed (e.g. for psycopg2)
# but psycopg2-binary is used, so slim should be enough.

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY pipelineprobe/ ./pipelineprobe/

ENTRYPOINT ["pipelineprobe"]
CMD ["--help"]
