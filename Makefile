COMPOSE_FILE ?= docker-compose.local.yml
ENV_FILE ?= .env.local
HEALTH_RETRIES ?= 30
COMPOSE = docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE)

.PHONY: help dev migrate api worker health smoke test test-unit-pure test-db-invariant test-db-direct test-db-pooler test-fail-visible-tenant-context test-celery-eager test-celery-worker test-celery-worker-concurrent test-pooler-worker-concurrent test-broker-topology test-parallel-isolation test-b23-representative test-b24-persistence-readiness test-b24-persistence-entry-gate test-governance test-e2e test-external-db-smoke down logs contracts-check contracts-validate contracts-check-auth contracts-check-attribution models-generate mocks-start mocks-stop mocks-restart tests-integration backend-test frontend-test

help: ## Show this help message
	@echo "SKELDIR 2.0 Monorepo - Available Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

$(ENV_FILE):
	@cp .env.local.example $(ENV_FILE)
	@echo "Created $(ENV_FILE) from .env.local.example"

dev: $(ENV_FILE) ## Start canonical local Postgres dependency; the Celery broker/result backend is Postgres-backed
	@$(COMPOSE) up -d postgres

migrate: $(ENV_FILE) ## Apply Alembic head inside the backend container against local Postgres
	@$(COMPOSE) run --rm migrate

api: $(ENV_FILE) ## Start the FastAPI service through Docker Compose
	@$(COMPOSE) up -d api

worker: $(ENV_FILE) ## Start the Celery worker through Docker Compose
	@$(COMPOSE) up -d worker

health: $(ENV_FILE) ## Check canonical API readiness endpoint from inside the API container
	@i=1; while [ $$i -le $(HEALTH_RETRIES) ]; do \
		if $(COMPOSE) exec -T api python -c "import json, urllib.request; r=urllib.request.urlopen('http://localhost:8000/health/ready', timeout=10); body=json.loads(r.read().decode()); assert r.status == 200 and body.get('status') == 'ok', body; print(json.dumps(body, sort_keys=True))"; then \
			exit 0; \
		fi; \
		i=$$((i + 1)); \
		sleep 2; \
	done; \
	echo "API readiness check failed after $(HEALTH_RETRIES) attempts"; \
	exit 1

smoke: $(ENV_FILE) ## Run the non-vacuous M1 runtime smoke proof inside the canonical topology
	@$(COMPOSE) run --rm smoke

test: $(ENV_FILE) ## Run safe default M2 feedback loop subset; no external DB/broker
	@bash scripts/ci/run_m2_test_feedback_loop.sh default

test-unit-pure: ## Run pure Python tests with no DB, broker, or network dependency
	@bash scripts/ci/run_m2_test_feedback_loop.sh unit-pure

test-db-invariant: ## Run real local Postgres invariant tests for RLS/GUC/triggers/constraints
	@bash scripts/ci/run_m2_test_feedback_loop.sh db-invariant

test-db-direct: ## Run local direct Postgres integration profile
	@bash scripts/ci/run_m2_test_feedback_loop.sh db-direct

test-db-pooler: ## Run local transaction-pooler profile
	@bash scripts/ci/run_m2_test_feedback_loop.sh db-pooler

test-fail-visible-tenant-context: ## Prove missing tenant context fails visibly
	@bash scripts/ci/run_m2_test_feedback_loop.sh fail-visible-tenant-context

test-celery-eager: ## Run Celery eager task-logic classification tests only
	@bash scripts/ci/run_m2_test_feedback_loop.sh celery-eager

test-celery-worker: ## Run real broker/worker topology classification tests
	@bash scripts/ci/run_m2_test_feedback_loop.sh celery-worker

test-celery-worker-concurrent: ## Prove real concurrent Celery tenant isolation
	@bash scripts/ci/run_m2_test_feedback_loop.sh celery-worker-concurrent

test-pooler-worker-concurrent: ## Prove concurrent worker tenant isolation through transaction pooler
	@bash scripts/ci/run_m2_test_feedback_loop.sh pooler-worker-concurrent

test-broker-topology: ## Prove local broker topology and external broker rejection
	@bash scripts/ci/run_m2_test_feedback_loop.sh broker-topology

test-parallel-isolation: ## Prove serial/parallel isolation and test namespace authority
	@bash scripts/ci/run_m2_test_feedback_loop.sh parallel-isolation

test-b23-representative: ## Run representative local B2.3 schema/path proof
	@bash scripts/ci/run_m2_test_feedback_loop.sh b23-representative

test-b24-persistence-readiness: ## Audit or block B2.4 persistence substrate readiness
	@bash scripts/ci/run_m2_test_feedback_loop.sh b24-persistence-readiness

test-b24-persistence-entry-gate: ## Run canonical B2.4 persistence entry-gate guard
	@bash scripts/ci/run_m2_test_feedback_loop.sh b24-persistence-entry-gate

test-governance: ## Run M2 governance/static validator
	@bash scripts/ci/run_m2_test_feedback_loop.sh governance

test-e2e: ## Run explicitly marked e2e tests
	@bash scripts/ci/run_m2_test_feedback_loop.sh e2e

test-external-db-smoke: ## Opt-in external DB smoke only; requires SKELDIR_ALLOW_EXTERNAL_DB_TESTS=true
	@bash scripts/ci/run_m2_test_feedback_loop.sh external-db-smoke

down: $(ENV_FILE) ## Stop the canonical local topology
	@$(COMPOSE) down --remove-orphans

logs: $(ENV_FILE) ## Show API and worker logs from the canonical local topology
	@$(COMPOSE) logs --tail=200 api worker

contracts-check: ## Bundle and validate all OpenAPI contracts (recommended)
	@echo "Running contract validation pipeline..."
	@bash scripts/contracts/check.sh

contracts-check-smoke: ## Bundle, validate, and run model generation smoke test
	@echo "Running contract validation with model generation smoke test..."
	@bash scripts/contracts/check.sh smoke

contracts-check-auth: ## Bundle and validate auth contract only
	@bash scripts/contracts/check.sh false auth

contracts-check-attribution: ## Bundle and validate attribution contract only
	@bash scripts/contracts/check.sh false attribution

contracts-validate: ## Validate all OpenAPI contracts (legacy - use contracts-check instead)
	@echo "Validating OpenAPI contracts..."
	@for file in api-contracts/openapi/v1/**/*.yaml api-contracts/openapi/v1/_common/*.yaml; do \
		if [ -f "$$file" ]; then \
			echo "Validating $$file..."; \
			npx @openapitools/openapi-generator-cli validate -i "$$file" || exit 1; \
		fi; \
	done
	@echo "All contracts validated successfully"

models-generate: ## Generate Pydantic models from contracts
	@echo "Generating Pydantic models..."
	@bash scripts/generate-models.sh

mocks-start: ## Start all Prism mock servers
	@echo "Starting mock servers..."
	@bash scripts/start-mocks.sh

mocks-stop: ## Stop all Prism mock servers
	@echo "Stopping mock servers..."
	@bash scripts/stop-mocks.sh

mocks-restart: ## Restart all Prism mock servers
	@echo "Restarting mock servers..."
	@bash scripts/restart-mocks.sh all

tests-integration: ## Run Playwright integration tests
	@echo "Running integration tests..."
	@npx playwright test

backend-test: ## Run backend unit tests
	@echo "Running backend tests..."
	@cd backend && pytest

frontend-test: ## Run frontend tests
	@echo "Running frontend tests..."
	@cd frontend && npm test

install: ## Install all dependencies
	@echo "Installing root dependencies..."
	@npm install
	@echo "Installing backend dependencies..."
	@cd backend && pip install -r requirements.txt || echo "Backend requirements.txt not found"
	@echo "Installing frontend dependencies..."
	@cd frontend && npm install || echo "Frontend package.json not found"

clean: ## Clean build artifacts
	@echo "Cleaning build artifacts..."
	@rm -rf backend/.pytest_cache backend/.coverage backend/htmlcov
	@rm -rf frontend/node_modules frontend/.next frontend/dist frontend/build
	@rm -rf test-results playwright-report
	@rm -rf tmp/

contract-check-conformance: ## Check contract-implementation conformance
	@echo "Checking contract-implementation conformance..."
	@python scripts/contracts/dump_routes.py
	@python scripts/contracts/dump_contract_ops.py
	@python scripts/contracts/check_static_conformance.py

contract-test-dynamic: ## Run dynamic contract tests
	@echo "Running dynamic contract tests..."
	@cd tests/contract && pytest test_contract_semantics.py -v

contract-enforce-full: ## Run full enforcement pipeline
	@echo "Running full contract enforcement pipeline..."
	@$(MAKE) contract-check-conformance
	@$(MAKE) contract-test-dynamic
	@echo "✅ Contract enforcement complete"

contract-print-scope: ## Print route classification
	@python scripts/contracts/print_scope_routes.py

contract-integrity: ## Run contract integrity tests (mocks vs contracts)
	@echo "Running contract integrity tests..."
	@cd tests/contract && pytest test_mock_integrity.py -v

contract-provider: ## Run provider contract tests (implementation vs contracts)
	@echo "Running provider contract tests..."
	@cd tests/contract && pytest test_contract_semantics.py -v

contract-full: ## Run full contract pipeline (bundle -> integrity -> provider -> docs)
	@echo "Running full contract enforcement pipeline..."
	@bash scripts/contracts/bundle.sh
	@$(MAKE) contract-integrity
	@$(MAKE) contract-provider
	@echo "✅ Full contract pipeline complete"

domain-map: ## Print domain mapping for mock servers
	@python scripts/contracts/print_domain_map.py

mocks-switch: ## Switch on-demand mock (usage: make mocks-switch DOMAIN=reconciliation)
	@bash scripts/switch-mock.sh $(DOMAIN)

docs-build: ## Build API documentation from contracts
	@echo "Building API documentation..."
	@bash scripts/contracts/build_docs.sh

docs-validate: ## Validate built documentation
	@echo "Validating API documentation..."
	@python scripts/contracts/validate_docs.py

docs-view: ## Open documentation index in browser
	@echo "Opening documentation..."
	@open api-contracts/dist/docs/v1/index.html || xdg-open api-contracts/dist/docs/v1/index.html || start api-contracts/dist/docs/v1/index.html
