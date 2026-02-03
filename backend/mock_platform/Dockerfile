FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/mock_platform /app/mock_platform
ENV PYTHONPATH=/app
WORKDIR /app

CMD ["uvicorn", "mock_platform.app:app", "--host", "0.0.0.0", "--port", "8080"]
