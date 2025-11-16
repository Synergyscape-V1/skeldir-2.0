# Webhooks Service Dockerfile
# Purpose: Extract webhooks service as standalone microservice

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/app/webhooks/ ./app/webhooks/
COPY backend/app/schemas/ ./app/schemas/
COPY backend/app/__init__.py ./app/

# Set environment variables
ENV PYTHONPATH=/app
ENV SERVICE_NAME=webhooks
ENV PORT=8004
ENV INGESTION_SERVICE_URL=http://ingestion-service:8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8004/api/health')" || exit 1

# Expose port
EXPOSE 8004

# Run service
CMD ["uvicorn", "app.webhooks.main:app", "--host", "0.0.0.0", "--port", "8004"]

