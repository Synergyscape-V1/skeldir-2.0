# Corrective X artifact law: the base image is digest-pinned so the
# tested artifact cannot float under a mutable tag. Update the pin
# deliberately (docker pull + inspect RepoDigest) when the base needs
# a security refresh; every refresh re-proves the image.
FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY contracts/trust-api /app/contracts/trust-api
COPY contracts/reconciliation /app/contracts/reconciliation
COPY contracts-internal/governance /app/contracts-internal/governance
COPY db/channel_mapping.yaml /app/db/channel_mapping.yaml
# Corrective X automatic consumption: the conduction-health probe ships
# inside the image so container healthchecks and platform alerting
# consume the independent P2 observer from the exact tested artifact.
COPY scripts/ops/conduction_health_probe.py /app/scripts/ops/conduction_health_probe.py
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
