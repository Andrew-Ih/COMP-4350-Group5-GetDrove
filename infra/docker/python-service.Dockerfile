# One Dockerfile for all five Python services. Pick the service with a build argument:
#   docker build -f infra/docker/python-service.Dockerfile --build-arg SERVICE=trips .
# (Docker Compose passes SERVICE for each service; run builds from the repo root.)

ARG PYTHON_IMAGE=python:3.13-slim

# ---------------------------------------------------------------- build stage
FROM ${PYTHON_IMAGE} AS build
ARG SERVICE
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src

# 1. Install third-party dependencies only. This layer is cached until uv.lock or a
#    pyproject.toml changes, so code-only changes rebuild in seconds.
COPY pyproject.toml uv.lock ./
COPY libs/common-web/pyproject.toml libs/common-web/
COPY libs/common-security/pyproject.toml libs/common-security/
COPY libs/events/pyproject.toml libs/events/
COPY services/accounts/pyproject.toml services/accounts/
COPY services/trips/pyproject.toml services/trips/
COPY services/routing/pyproject.toml services/routing/
COPY services/payments/pyproject.toml services/payments/
COPY services/notifications/pyproject.toml services/notifications/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${SERVICE}" --no-install-workspace

# 2. Install the shared libraries and this service themselves (not editable, so the
#    runtime image only needs the virtual environment).
COPY libs ./libs
COPY services ./services
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "${SERVICE}" --no-editable

# ---------------------------------------------------------------- runtime stage
FROM ${PYTHON_IMAGE} AS runtime
ARG SERVICE
ENV SERVICE=${SERVICE} \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# Alembic needs its config and migration scripts at runtime.
COPY services/${SERVICE}/alembic.ini /app/alembic.ini
COPY services/${SERVICE}/migrations /app/migrations
COPY infra/docker/entrypoint.sh /app/entrypoint.sh
# Files can arrive owner-only depending on the host; make everything readable for the app user.
RUN chmod -R a+rX /app && chmod 755 /app/entrypoint.sh

USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"]

ENTRYPOINT ["/app/entrypoint.sh"]
