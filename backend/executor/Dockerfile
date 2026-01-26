# Executor Dockerfile - Hardened Python runtime for sandboxed code execution
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for execution
RUN groupadd -r executor && useradd -r -g executor executor

WORKDIR /app

# Install only the executor module (minimal dependencies)
COPY executor/ ./executor/
COPY pyproject.toml ./

# Install minimal dependencies needed for executor
RUN pip install pydantic pydantic-settings

# Create a read-only code directory
RUN mkdir -p /code && chown executor:executor /code

# Switch to non-root user
USER executor

# Set restrictive permissions
WORKDIR /code

# The entrypoint will be the runner module
ENTRYPOINT ["python", "-m", "executor.runner"]
