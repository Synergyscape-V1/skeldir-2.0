# SKELDIR Backend

FastAPI application implementing the Skeldir Attribution Intelligence backend.

## Structure

```
backend/
├── app/              # Application code
│   ├── ingestion/    # Event ingestion service
│   ├── attribution/   # Statistical attribution models
│   ├── auth/          # Authentication and authorization
│   └── webhooks/      # Webhook handlers
├── db/                # Database infrastructure
│   ├── migrations/    # Alembic migrations
│   ├── seeds/         # Seed data
│   └── snapshots/     # Schema snapshots
├── alembic/           # Alembic configuration
├── tests/             # Backend unit tests
└── requirements.txt   # Python dependencies
```

## Status

**Note:** Backend application code is not yet migrated. This directory structure is prepared for when backend code is available.

## Development

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Run tests
pytest
```

### Architecture

The backend is structured as a **modular monolith** with strict component boundaries:

- **Ingestion**: Event ingestion with idempotency and dead letter queue
- **Attribution**: Statistical attribution models (Bayesian MMM, deterministic)
- **Auth**: Authentication and authorization with tenant isolation
- **Webhooks**: Webhook handlers for Shopify, WooCommerce, Stripe, PayPal

Each component is developed with decoupled boundaries and clear API contracts, enabling future microservices extraction without architectural rewrites.

## Technology Stack

- **API Framework**: FastAPI 0.104+ with Pydantic 2.0+
- **Database**: PostgreSQL 15+ with Row-Level Security (RLS)
- **Background Tasks**: Celery 5.3+ with PostgreSQL broker
- **Observability**: OpenTelemetry, Prometheus, Grafana, Sentry
- **Testing**: pytest, pytest-asyncio

## Contract-First Development

All API endpoints are defined in `contracts/{domain}/v1/` before implementation. Pydantic models are auto-generated from contracts:

```bash
# Generate models from contracts
bash scripts/generate-models.sh
```

Models are generated in `backend/app/schemas/`.

## Database

Database migrations are managed via Alembic:

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

Migrations are located in `backend/db/migrations/`.

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest backend/tests/test_attribution.py

# Run with coverage
pytest --cov=backend/app --cov-report=html
```

## Documentation

- [Architecture Guide](../.cursor/rules)
- [Database Documentation](../docs/database/)
- [Development Workflow](../docs/DEVELOPMENT_WORKFLOW.md)

