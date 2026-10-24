FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY backend/requirements-lock.txt /app/backend/requirements-lock.txt
# XVI (H-XVI-R18): the production image installs the fully pinned lock
# file, not the floating requirements range, so a rebuilt image from
# the same tree resolves byte-identical dependencies. requirements.txt
# remains the human-edited range; the lock is the build authority.
RUN pip install --no-cache-dir -r /app/backend/requirements-lock.txt

COPY backend /app/backend
ARG B26_P2_HISTORY_WITNESS_PUBLIC_KEY_SHA256=""
ARG B26_P2_HISTORY_WITNESS_GENESIS_HASH=""
RUN python - <<'PY'
import os
from pathlib import Path

public_key_sha256 = os.environ.get(
    "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_SHA256", ""
).strip()
genesis_hash = os.environ.get(
    "B26_P2_HISTORY_WITNESS_GENESIS_HASH", ""
).strip()
target = Path("/app/backend/app/trust/witness_anchor.py")
text = target.read_text(encoding="utf-8")
text = text.replace(
    "COMPILED_PUBLIC_KEY_SHA256: str | None = None",
    f"COMPILED_PUBLIC_KEY_SHA256: str | None = {public_key_sha256!r}",
)
text = text.replace(
    "COMPILED_GENESIS_HASH: str | None = None",
    f"COMPILED_GENESIS_HASH: str | None = {genesis_hash!r}",
)
target.write_text(text, encoding="utf-8")
PY
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY contracts/trust-api /app/contracts/trust-api
COPY contracts/reconciliation /app/contracts/reconciliation
COPY contracts-internal/governance /app/contracts-internal/governance
COPY db/channel_mapping.yaml /app/db/channel_mapping.yaml
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
