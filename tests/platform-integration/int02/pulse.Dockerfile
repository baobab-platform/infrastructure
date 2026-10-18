# Actual Pulse source and frozen provider-owned lock. This is not a substitute
# API: the entrypoint is the owning engine's normal production composition.
FROM ghcr.io/astral-sh/uv:0.8.17@sha256:e4644cb5bd56fdc2c5ea3ee0525d9d21eed1603bccd6a21f887a938be7e85be1 AS uv
FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56
COPY --from=uv /uv /bin/uv
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY scripts/migrate.py ./scripts/migrate.py
COPY migrations ./migrations
RUN uv sync --frozen --no-dev && useradd --uid 1000 --create-home pulse
ENV PATH="/app/.venv/bin:${PATH}" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER pulse
ENTRYPOINT ["uvicorn", "baobab_pulse.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
