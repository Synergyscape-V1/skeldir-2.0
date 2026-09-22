FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY scripts/ops /app/scripts/ops
COPY contracts/trust-api /app/contracts/trust-api
COPY contracts/reconciliation /app/contracts/reconciliation
COPY contracts-internal/governance /app/contracts-internal/governance
COPY db/channel_mapping.yaml /app/db/channel_mapping.yaml
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

# B2.6-P2 Corrective IX: container-level conduction signal. The probe
# consumes the shipping observer path (API + DB + evaluator + scheduler)
# via GET /health/b26-p2-conduction and fails closed on scheduler or
# evaluator absence. Compose overrides the URL for non-API services
# (relay/beat probe via http://api:8000); workers/signer disable it.
HEALTHCHECK --interval=60s --timeout=10s --retries=3 CMD python /app/scripts/ops/conduction_health_probe.py --url http://localhost:8000/health/b26-p2-conduction || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
