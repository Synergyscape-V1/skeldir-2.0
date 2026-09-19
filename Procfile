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
worker: cd backend && celery -A app.celery_app.celery_app worker --loglevel=info --queues=housekeeping,maintenance,llm,attribution
# The Bayesian worker is the only process that plans fits and writes Bayesian
# truth, so it is the only one that runs on the dedicated app_worker login.
# Foreman-style managers share one environment, so this line must override
# DATABASE_URL explicitly -- inheriting the API DSN would hand worker
# authority to a process topology that is supposed to be separated from it.
worker_bayesian: cd backend && SKELDIR_CELERY_WORKER_ROLE=bayesian DATABASE_URL=$WORKER_DATABASE_URL SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS=1 celery -A app.celery_app.celery_app worker --loglevel=info --queues=bayesian
# Fresh cross-tenant dispatch is a separate process and credential.  It cannot
# execute fits and the ordinary Bayesian worker never receives its queue or DSN.
worker_bayesian_publisher: cd backend && SKELDIR_CELERY_WORKER_ROLE=bayesian_publisher DATABASE_URL=$PUBLISHER_DATABASE_URL B24_DISPATCH_PUBLISHER_DATABASE_URL=$PUBLISHER_DATABASE_URL celery -A app.celery_app.celery_app worker --loglevel=info --queues=bayesian_publisher --concurrency=1
# The B2.3 worker authors verdict truth and must never mint dispatch
# authority: it runs under the dedicated B2.3 worker credential
# (B2.6-P2 Corrective IV), never the API DSN. B23_WORKER_DATABASE_URL is
# deliberately distinct from WORKER_DATABASE_URL, which names the
# B2.5-P13 C7 bayesian credential -- C7 separation is preserved because
# no non-bayesian process reads the bayesian variable (see
# validate_b25_p13_c7_closure.py token-match rule). Both DATABASE_URL and
# B23_WORKER_DATABASE_URL resolve to the worker credential inside this
# process so no in-process pool retains producer authority; an unset
# variable fails closed at import (SKELDIR_B23_REQUIRE_WORKER_DSN).
worker_b23: cd backend && DATABASE_URL=$B23_WORKER_DATABASE_URL B23_WORKER_DATABASE_URL=$B23_WORKER_DATABASE_URL SKELDIR_B23_REQUIRE_WORKER_DSN=1 celery -A app.celery_app.celery_app worker --loglevel=info --queues=b23_match_engine --concurrency=${B23_WORKER_CONCURRENCY:-2} --prefetch-multiplier=1
# B2.6-P2 Corrective III recovery process: sweeps pending execution intents
# to the broker with stable task identity. Corrective V: runs under the
# dedicated relay credential (B26_P2_RELAY_DATABASE_URL, login app_relay),
# never the API DSN. The relay recovers/publishes EXISTING execution
# authority (SELECT + delivery-column UPDATE + broker DML); it cannot mint
# execution authority (no INSERT anywhere, no conduction-gate EXECUTE).
# An unset variable fails closed at import (require_secret) instead of
# silently inheriting the producer DSN (which would hand the recovery
# process full authority-mint capability).
# Supervision (Corrective IV H-IV-B07): foreman-style managers (overmind,
# honcho, foreman) restart crashed processes automatically; local
# container deployments use `restart: unless-stopped` (see the local
# compose manifest). This matters because a transient broker fault can
# kill a Celery process
# and the recovery motor must come back without human action. (A faulted
# broker session no longer wedges the scheduler even without a restart:
# the HealingBeatScheduler drops poisoned broker state on apply failure;
# see backend/app/celery_beat.py.)
relay_b26_p2: cd backend && DATABASE_URL=$B26_P2_RELAY_DATABASE_URL SKELDIR_CELERY_WORKER_ROLE=b26_p2_relay celery -A app.celery_app.celery_app worker --loglevel=info --queues=b26_p2_relay --concurrency=1 --prefetch-multiplier=1
# B2.6-P2 Corrective V: the scheduler holds broker-scheduling authority
# only (login app_beat: broker DML, no application-table authority). It
# must never inherit the API DSN; an unset variable fails closed.
beat: cd backend && DATABASE_URL=$B26_P2_BEAT_DATABASE_URL celery -A app.celery_app.celery_app beat --loglevel=info

# Mock Servers (Contract-First Development)
mock_auth: prism mock api-contracts/dist/openapi/v1/auth.bundled.yaml -p 4010 -h 0.0.0.0
mock_attribution: prism mock api-contracts/dist/openapi/v1/attribution.bundled.yaml -p 4011 -h 0.0.0.0
mock_reconciliation: prism mock api-contracts/dist/openapi/v1/reconciliation.bundled.yaml -p 4012 -h 0.0.0.0
mock_export: prism mock api-contracts/dist/openapi/v1/export.bundled.yaml -p 4013 -h 0.0.0.0
mock_health: prism mock api-contracts/dist/openapi/v1/health.bundled.yaml -p 4014 -h 0.0.0.0
mock_privacy: prism mock api-contracts/dist/openapi/v1/privacy.bundled.yaml -p 4019 -h 0.0.0.0
mock_shopify: prism mock api-contracts/dist/openapi/v1/webhooks.shopify.bundled.yaml -p 4015 -h 0.0.0.0
mock_woocommerce: prism mock api-contracts/dist/openapi/v1/webhooks.woocommerce.bundled.yaml -p 4016 -h 0.0.0.0
mock_stripe: prism mock api-contracts/dist/openapi/v1/webhooks.stripe.bundled.yaml -p 4017 -h 0.0.0.0
mock_paypal: prism mock api-contracts/dist/openapi/v1/webhooks.paypal.bundled.yaml -p 4018 -h 0.0.0.0
mock_llm_investigations: prism mock api-contracts/dist/openapi/v1/llm-investigations.bundled.yaml -p 4024 -h 0.0.0.0
mock_llm_budget: prism mock api-contracts/dist/openapi/v1/llm-budget.bundled.yaml -p 4025 -h 0.0.0.0
mock_llm_explanations: prism mock api-contracts/dist/openapi/v1/llm-explanations.bundled.yaml -p 4026 -h 0.0.0.0
