FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# psql is used by docker-compose.e2e.yml's migrate service for role/bootstrap DDL.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements-dev.txt /app/backend/requirements-dev.txt
RUN python -m pip install --upgrade pip \
    && pip install -r /app/backend/requirements.txt

# Backend code + migrations
COPY backend /app/backend
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

# Some migrations/scripts reference repo-level db artifacts.
COPY db /app/db

ENV PYTHONPATH=/app/backend

