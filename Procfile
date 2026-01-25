# Skeldir Multi-Process Orchestration - Phase D Runtime Infrastructure
# Replit-native process management for coordinated service execution
#
# Service Architecture:
#   - db: PostgreSQL database (port 5432, unix socket)
#   - queue: Postgres-backed Celery broker (no external queue service)
#   - web: FastAPI application (port 8000)
#   - worker: Celery background worker
#   - mocks: Prism contract mock servers (ports 4010+)
#
# Usage:
#   - Replit: Automatically started
#   - Local: overmind start (or foreman start)
#   - Mocks only: bash scripts/start-mocks.sh

# Core Services
db: postgres -D $PGDATA -k $PGSOCKET -h localhost -p 5432
web: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
worker: cd backend && celery -A app.tasks worker --loglevel=info
beat: cd backend && celery -A app.celery_app.celery_app beat --loglevel=info

# Mock Servers (Contract-First Development)
mock_auth: prism mock api-contracts/dist/openapi/v1/auth.bundled.yaml -p 4010 -h 0.0.0.0
mock_attribution: prism mock api-contracts/dist/openapi/v1/attribution.bundled.yaml -p 4011 -h 0.0.0.0
mock_reconciliation: prism mock api-contracts/dist/openapi/v1/reconciliation.bundled.yaml -p 4012 -h 0.0.0.0
mock_export: prism mock api-contracts/dist/openapi/v1/export.bundled.yaml -p 4013 -h 0.0.0.0
mock_health: prism mock api-contracts/dist/openapi/v1/health.bundled.yaml -p 4014 -h 0.0.0.0
mock_shopify: prism mock api-contracts/dist/openapi/v1/webhooks.shopify.bundled.yaml -p 4015 -h 0.0.0.0
mock_woocommerce: prism mock api-contracts/dist/openapi/v1/webhooks.woocommerce.bundled.yaml -p 4016 -h 0.0.0.0
mock_stripe: prism mock api-contracts/dist/openapi/v1/webhooks.stripe.bundled.yaml -p 4017 -h 0.0.0.0
mock_paypal: prism mock api-contracts/dist/openapi/v1/webhooks.paypal.bundled.yaml -p 4018 -h 0.0.0.0
mock_llm_investigations: prism mock api-contracts/dist/openapi/v1/llm-investigations.bundled.yaml -p 4024 -h 0.0.0.0
mock_llm_budget: prism mock api-contracts/dist/openapi/v1/llm-budget.bundled.yaml -p 4025 -h 0.0.0.0
mock_llm_explanations: prism mock api-contracts/dist/openapi/v1/llm-explanations.bundled.yaml -p 4026 -h 0.0.0.0
