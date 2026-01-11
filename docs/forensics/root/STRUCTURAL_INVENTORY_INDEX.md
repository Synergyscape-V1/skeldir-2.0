# STRUCTURAL INVENTORY INDEX
**Quick Reference for FORENSIC_STRUCTURAL_MAP.md**

## Navigation Guide

### For Different Roles

**🔧 Backend Engineers**
1. Start: [FORENSIC_STRUCTURAL_MAP.md](FORENSIC_STRUCTURAL_MAP.md#section-2-backend-application-structure) → Section 2: Backend Application Structure
2. Read: [db/GOVERNANCE_BASELINE_CHECKLIST.md](db/GOVERNANCE_BASELINE_CHECKLIST.md)
3. Reference: [db/schema/canonical_schema.sql](db/schema/canonical_schema.sql)
4. Check: [backend/app/main.py](backend/app/main.py) and [backend/app/api/](backend/app/api/)

**🗄️ Database Engineers**
1. Start: [FORENSIC_STRUCTURAL_MAP.md](FORENSIC_STRUCTURAL_MAP.md#section-3-database--migration-system) → Section 3: Database & Migration System
2. Review: [alembic/versions/](alembic/versions/) (3 phases: 001_core_schema, 002_pii_controls, 003_data_governance)
3. Study: [db/schema/ACCEPTANCE_RULES.md](db/schema/ACCEPTANCE_RULES.md)
4. Understand: [db/docs/MIGRATION_SYSTEM.md](db/docs/MIGRATION_SYSTEM.md)

**📋 API/Contract Engineers**
1. Start: [FORENSIC_STRUCTURAL_MAP.md](FORENSIC_STRUCTURAL_MAP.md#section-5-api-contracts--specifications) → Section 5: API Contracts & Specifications
2. Review: [contracts/README.md](contracts/README.md)
3. Check: [api-contracts/governance/invariants.yaml](api-contracts/governance/invariants.yaml)
4. Test: [tests/contract/](tests/contract/)

**🧪 Test/QA Engineers**
1. Start: [FORENSIC_STRUCTURAL_MAP.md](FORENSIC_STRUCTURAL_MAP.md#section-4-test-structure) → Section 4: Test Structure
2. Backend tests: [backend/tests/](backend/tests/)
3. Integration tests: [tests/](tests/)
4. Database tests: [db/tests/](db/tests/)

**🚀 DevOps/Infrastructure**
1. Start: [FORENSIC_STRUCTURAL_MAP.md](FORENSIC_STRUCTURAL_MAP.md#section-7-configuration-files) → Section 7: Configuration Files
2. CI/CD: [.github/workflows/](github/workflows/) (13 workflow files)
3. Docker: [docker-compose.mock.yml](docker-compose.mock.yml), [docker-compose.component-dev.yml](docker-compose.component-dev.yml)
4. Scripts: [scripts/](scripts/) (38 files)

**📚 Documentation/Product**
1. Start: [docs/README.md](docs/README.md)
2. Governance: [db/docs/](db/docs/)
3. Deployment: [docs/deployment/](docs/deployment/)
4. Quick guides: [docs/quick-reference/](docs/quick-reference/)

---

## Directory Quick Lookup

| What I Need | Primary Location | Secondary |
|-------------|-----------------|-----------|
| **HTTP Routes** | [backend/app/api/](backend/app/api/) | [contracts/](contracts/) |
| **Database Schema** | [db/schema/canonical_schema.sql](db/schema/canonical_schema.sql) | [alembic/versions/](alembic/versions/) |
| **Migrations** | [alembic/versions/](alembic/versions/) | [db/migrations/templates/](db/migrations/templates/) |
| **API Contracts** | [contracts/](contracts/) | [api-contracts/openapi/v1/](api-contracts/openapi/v1/) |
| **Tests** | [tests/](tests/), [backend/tests/](backend/tests/) | [db/tests/](db/tests/) |
| **Scripts** | [scripts/](scripts/) | [Makefile](Makefile) |
| **Documentation** | [docs/](docs/) | [db/docs/](db/docs/) |
| **CI/CD** | [.github/workflows/](github/workflows/) | [Makefile](Makefile) |
| **Governance** | [AGENTS.md](AGENTS.md) | [db/GOVERNANCE_BASELINE_CHECKLIST.md](db/GOVERNANCE_BASELINE_CHECKLIST.md) |

---

## Critical File Paths (Canonical References)

### Architectural Mandate
- **[AGENTS.md](AGENTS.md)** ← SINGLE SOURCE OF TRUTH

### Database
- **[alembic.ini](alembic.ini)** - Migration runner config
- **[db/schema/canonical_schema.sql](db/schema/canonical_schema.sql)** - Complete DDL
- **[db/OWNERSHIP.md](db/OWNERSHIP.md)** - Team assignments
- **[db/GOVERNANCE_BASELINE_CHECKLIST.md](db/GOVERNANCE_BASELINE_CHECKLIST.md)** - Phase checklist

### API
- **[contracts/](contracts/)** - Source specs (YAML)
- **[api-contracts/openapi/v1/](api-contracts/openapi/v1/)** - Bundled specs
- **[api-contracts/governance/invariants.yaml](api-contracts/governance/invariants.yaml)** - Port, header, auth rules
- **[backend/app/main.py](backend/app/main.py)** - FastAPI initialization

### Backend Code
- **[backend/app/api/](backend/app/api/)** - Route handlers
- **[backend/app/schemas/](backend/app/schemas/)** - Pydantic models
- **[backend/app/ingestion/channel_normalization.py](backend/app/ingestion/channel_normalization.py)** - Webhook event normalization
- **[backend/app/middleware/pii_stripping.py](backend/app/middleware/pii_stripping.py)** - PII redaction
- **[backend/app/tasks/maintenance.py](backend/app/tasks/maintenance.py)** - Celery tasks

### Testing
- **[tests/contract/](tests/contract/)** - API contract tests
- **[backend/tests/integration/](backend/tests/integration/)** - Data retention, PII tests
- **[db/tests/](db/tests/)** - Database validation tests

### Scripts
- **[scripts/start-mocks.sh](scripts/start-mocks.sh)** ← CANONICAL mock startup
- **[scripts/contracts/check.sh](scripts/contracts/check.sh)** - Contract validation pipeline
- **[scripts/phase_gates/run_gate.py](scripts/phase_gates/run_gate.py)** - Phase gate enforcement
- **[scripts/validate-schema-compliance.py](scripts/validate-schema-compliance.py)** - Schema audit

### Documentation
- **[docs/README.md](docs/README.md)** - Documentation index
- **[docs/BINARY_GATES.md](docs/BINARY_GATES.md)** - Phase gate definitions
- **[docs/CONTRACTS_QUICKSTART.md](docs/CONTRACTS_QUICKSTART.md)** - Contract onboarding
- **[docs/deployment/](docs/deployment/)** - Deployment procedures

### CI/CD
- **[.github/workflows/ci.yml](.github/workflows/ci.yml)** - Main CI pipeline
- **[.github/workflows/contract-validation.yml](.github/workflows/contract-validation.yml)** - API governance
- **[.github/workflows/empirical-validation.yml](.github/workflows/empirical-validation.yml)** - Evidence collection
- **[.github/workflows/phase-gates.yml](.github/workflows/phase-gates.yml)** - Release control

---

## Phase Tracking

### Current Phase: B0.2-B0.3 (Infrastructure → Governance)

**Phase B0.1** (✓ Complete)
- API contracts defined
- Evidence: `contracts/` + baselines

**Phase B0.2** (🔄 In Progress)
- Frontend infrastructure
- Evidence: `frontend/` + mock endpoints
- Status: [docs/deployment/DEPLOYMENT_COMPLETE.md](docs/deployment/DEPLOYMENT_COMPLETE.md)

**Phase B0.3** (🔄 In Progress)
- Full governance baseline
- Evidence: `db/`, `alembic/versions/003_*`
- Status: `backend/validation/phase_ack/B0_3.json`

**Future Phases**
- B0.7+: LLM routing/caching
- B1.x: JWT/RBAC, privacy enforcement
- B2.x: Deterministic attribution, reconciliation

---

## Common Tasks & Where to Find Them

### "I need to understand the current database schema"
1. **Visual overview**: [db/schema/canonical_schema.yaml](db/schema/canonical_schema.yaml)
2. **Complete DDL**: [db/schema/canonical_schema.sql](db/schema/canonical_schema.sql)
3. **Field documentation**: [db/docs/DATA_DICTIONARY_GUIDE.md](db/docs/DATA_DICTIONARY_GUIDE.md)
4. **Live snapshot**: [db/schema/live_schema_snapshot.sql](db/schema/live_schema_snapshot.sql)

### "I need to add a new webhook vendor"
1. **Pattern**: Review [backend/app/schemas/webhooks_stripe.py](backend/app/schemas/webhooks_stripe.py)
2. **Integration map**: Add to [api-contracts/governance/integration-maps/](api-contracts/governance/integration-maps/)
3. **Contract**: Add YAML to [contracts/webhooks/v1/](contracts/webhooks/v1/)
4. **Tests**: Add to [api-contracts/governance/test-expectations/](api-contracts/governance/test-expectations/)
5. **Validation**: Run [scripts/contracts/check.sh](scripts/contracts/check.sh)

### "I need to understand PII controls"
1. **Governance**: [db/docs/](db/docs/) (search for "pii" or "audit")
2. **Database triggers**: [alembic/versions/002_pii_controls/](alembic/versions/002_pii_controls/)
3. **Middleware**: [backend/app/middleware/pii_stripping.py](backend/app/middleware/pii_stripping.py)
4. **Tests**: [backend/tests/integration/test_pii_guardrails.py](backend/tests/integration/test_pii_guardrails.py)
5. **Monitoring**: [monitoring/grafana/pii-dashboard.json](monitoring/grafana/pii-dashboard.json)

### "I need to check what the API looks like"
1. **Quick look**: [api-contracts/governance/invariants.yaml](api-contracts/governance/invariants.yaml) (ports, headers)
2. **Full spec**: [api-contracts/openapi/v1/attribution.bundled.yaml](api-contracts/openapi/v1/attribution.bundled.yaml)
3. **Interactive docs**: Run `make docs-serve` or visit `api-contracts/dist/docs/v1/index.html`
4. **Test cases**: [api-contracts/governance/test-expectations/](api-contracts/governance/test-expectations/)

### "I need to run tests"
1. **All tests**: `make test`
2. **Backend only**: `make test-backend`
3. **Integration**: `make test-integration`
4. **Contract validation**: `make contract-validate`
5. **Schema audit**: `make schema-validate`

### "I need to start the development environment"
1. **Mock servers**: [scripts/start-mocks.sh](scripts/start-mocks.sh)
2. **Full stack**: `docker-compose -f docker-compose.component-dev.yml up`
3. **Health check**: [scripts/health-check-mocks.sh](scripts/health-check-mocks.sh)
4. **Frontend config**: [env.frontend.b02.json](env.frontend.b02.json)

### "I need to add a database migration"
1. **Template**: [db/migrations/templates/](db/migrations/templates/)
2. **Example**: Review [alembic/versions/003_data_governance/202511131232_enhance_allocation_schema.py](alembic/versions/003_data_governance/202511131232_enhance_allocation_schema.py)
3. **Safety checklist**: [db/docs/MIGRATION_SAFETY_CHECKLIST.md](db/docs/MIGRATION_SAFETY_CHECKLIST.md)
4. **Run locally**: `alembic upgrade head`
5. **Validate**: `make schema-validate`

### "I need to understand how channel normalization works"
1. **Implementation**: [backend/app/ingestion/channel_normalization.py](backend/app/ingestion/channel_normalization.py)
2. **Mapping**: [db/channel_mapping.yaml](db/channel_mapping.yaml)
3. **Tests**: [backend/tests/test_channel_normalization.py](backend/tests/test_channel_normalization.py)
4. **Database**: [alembic/versions/003_data_governance/202511141310_create_channel_taxonomy.py](alembic/versions/003_data_governance/202511141310_create_channel_taxonomy.py)

---

## Naming & Organization Gotchas

### These directories do different things (don't confuse them):
```
contracts/                  ← Source YAML specs
api-contracts/              ← Bundled specs + governance
api-contracts/openapi/v1/   ← Bundled OpenAPI (consumption)
api-contracts/governance/   ← API rules + test data
```

### These scripts do similar things (but are different):
```
scripts/start-mocks.sh              ← ✓ USE THIS (canonical)
scripts/start-mock-servers.sh       ← Deprecated variant
scripts/start-mocks-prism.sh        ← Deprecated variant
scripts/start-prism-mocks.sh        ← Deprecated variant
```

### These phases track different things:
```
B0.1, B0.2, B0.3, ... B0.7, B1.x, B2.x  ← Platform phases
001_core_schema, 002_pii_controls, 003_data_governance  ← Migration phases (parallel numbering)
```

### These documents live in different places:
```
db/GOVERNANCE_BASELINE_CHECKLIST.md    ← Phase checklist
db/OWNERSHIP.md                        ← Team assignments
db/docs/                               ← Schema governance procedures
api-contracts/governance/              ← API rules & test expectations
scripts/governance/                    ← Governance validation scripts
```

---

## CI/CD Workflow Reference

### Before Making a PR

1. **Run tests locally**:
   ```bash
   make test                    # All tests
   make contract-validate       # API contracts
   make schema-validate         # Schema compliance
   ```

2. **Validate specific changes**:
   ```bash
   # For database changes:
   alembic upgrade head
   make schema-validate

   # For API changes:
   make contract-validate
   tests/contract/test_route_fidelity.py

   # For integrations:
   python scripts/validate_channel_integrity.py
   ```

### CI Workflows (Auto-Run on Push)

1. **ci.yml** - Unit tests, linting, type checks (must pass)
2. **contract-validation.yml** - API spec validation (must pass)
3. **empirical-validation.yml** - Evidence collection (gates next phase)
4. **phase-gates.yml** - Phase criteria enforcement (blocks merge if failed)

### Phase Gate Criteria

**B0.2 Gate** (currently active):
- All unit tests pass
- Contract validation passes
- Mock servers have all endpoints
- Frontend integration verified

**B0.3 Gate** (in progress):
- Database schema complete
- RLS verified on all tenant tables
- PII guardrails enforced
- Data retention policies tested

---

## Troubleshooting Reference

### "My test is failing, where do I look?"

| Test Type | Location | Debug Script |
|-----------|----------|--------------|
| Backend unit test | [backend/tests/](backend/tests/) | `make test-backend` |
| Integration test | [tests/](tests/) | `make test-integration` |
| Contract test | [tests/contract/](tests/contract/) | `make contract-validate` |
| Database test | [db/tests/](db/tests/) | `pytest db/tests/` |

### "Where are the invariants defined?"

**API Invariants**: [api-contracts/governance/invariants.yaml](api-contracts/governance/invariants.yaml)
- Ports: 4010-4026
- Headers: X-Correlation-ID, Authorization, If-None-Match
- Auth: JWT HS256, 1h access + 7d refresh
- Caching: 30s TTL on realtime endpoints

### "How do I generate models from the contract?"

1. Review: [contracts/](contracts/) source specs
2. Run: `make model-generate`
3. Check: [backend/app/schemas/](backend/app/schemas/) for generated Pydantic models

### "What happens if I push an incompatible API change?"

1. **oasdiff detects breaking change**
2. **CI blocks merge** (checks via `.github/workflows/contract-validation.yml`)
3. **Solution**: Bump major version (v1 → v2) and update baselines
4. **Reference**: [docs/PACKAGE_VERSIONING.md](docs/PACKAGE_VERSIONING.md)

---

## Document Architecture

### Documents by Audience

**For Architects**:
- [AGENTS.md](AGENTS.md) - Architectural mandate
- [db/GOVERNANCE_BASELINE_CHECKLIST.md](db/GOVERNANCE_BASELINE_CHECKLIST.md) - Phase structure
- [docs/BINARY_GATES.md](docs/BINARY_GATES.md) - Release criteria

**For Engineers (specific domains)**:
- Database: [db/docs/MIGRATION_SYSTEM.md](db/docs/MIGRATION_SYSTEM.md)
- API: [contracts/README.md](contracts/README.md)
- Ingestion: [api-contracts/governance/integration-maps/](api-contracts/governance/integration-maps/)
- Privacy: [db/docs/IMMUTABILITY_POLICY.md](db/docs/IMMUTABILITY_POLICY.md)

**For Operations**:
- Deployment: [docs/deployment/](docs/deployment/)
- Monitoring: [monitoring/](monitoring/)
- Troubleshooting: [docs/quick-reference/](docs/quick-reference/)

---

## Contact & Escalation

For questions about structural organization, refer to:
- **Architecture**: [AGENTS.md](AGENTS.md) (engineering lead)
- **Database**: [db/OWNERSHIP.md](db/OWNERSHIP.md) (see team assignments)
- **API Contracts**: [api-contracts/governance/](api-contracts/governance/) (check COVERAGE_MANIFEST)

---

**Last Updated**: 2025-12-07
**Related Document**: [FORENSIC_STRUCTURAL_MAP.md](FORENSIC_STRUCTURAL_MAP.md)
