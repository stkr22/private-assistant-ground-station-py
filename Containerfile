# Build stage: Python 3.13.9-trixie
FROM docker.io/library/python:3.13.9-trixie@sha256:f2578785b6c139fb4315a4e701a4d2412919ab6301b058eaf49766ce68c97536 AS build-python

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:0.9.11@sha256:5aa820129de0a600924f166aec9cb51613b15b68f1dcd2a02f31a500d2ede568 /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy the application into the container.
COPY pyproject.toml uv.lock README.md ./

# Install dependencies only (excluding the current package)
RUN --mount=type=cache,target=/root/.cache \
    uv venv && \
    uv sync --frozen --no-dev --no-install-project

# runtime stage: Python 3.13.9-slim-trixie
FROM docker.io/library/python:3.13.9-slim-trixie@sha256:326df678c20c78d465db501563f3492d17c42a4afe33a1f2bf5406a1d56b0e86

ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN addgroup --system --gid 1001 appuser && adduser --system --uid 1001 --no-create-home --ingroup appuser appuser

WORKDIR /app
# Copy virtual environment from build stage
COPY --from=build-python /app/.venv /app/.venv

COPY src/app /app/app

ENV PATH="/app/.venv/bin:$PATH"

# Set the user to 'appuser'
USER appuser

# Expose the application port
EXPOSE 8080

# Start the application as the non-root user
CMD ["fastapi", "run", "app/main.py", "--proxy-headers", "--host", "0.0.0.0", "--port", "8080"]
