FROM python:3.11-slim

WORKDIR /app

# Install the package (the build backend needs the package sources present).
COPY pyproject.toml README.md ./
COPY pipelineprobe/ ./pipelineprobe/
# Opt into cloud warehouses with: --build-arg PIP_EXTRAS="[cloud]"
ARG PIP_EXTRAS=""
RUN pip install --no-cache-dir ".${PIP_EXTRAS}"

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["pipelineprobe"]
CMD ["--help"]
