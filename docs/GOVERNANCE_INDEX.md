# Governance Framework Index

**Quick Navigation for Governance Rules Across SKELDIR 2.0**

---

## Entry Points by Role

| Role | Start Here |
|------|-----------|
| **Database Engineers** | [db/GOVERNANCE_BASELINE_CHECKLIST.md](../db/GOVERNANCE_BASELINE_CHECKLIST.md) |
| **API/Contract Engineers** | [api-contracts/governance/invariants.yaml](../api-contracts/governance/invariants.yaml) |
| **Backend Engineers** | [AGENTS.md](../AGENTS.md) (Architecture Mandate) |
| **DevOps/Infrastructure** | [docs/governance/](../docs/governance/) (Policy & Procedures) |
| **Everyone (First Time)** | This index! |

---

## Four Layers of Governance

### 1. Database Governance
**Location**: `db/`

**Purpose**: Schema design, immutability policies, data lifecycle, RLS enforcement

**Key Files**:
- [OWNERSHIP.md](../db/OWNERSHIP.md) - Table ownership, RLS policies, data stewardship
- [GOVERNANCE_BASELINE_CHECKLIST.md](../db/GOVERNANCE_BASELINE_CHECKLIST.md) - Phase gates, acceptance criteria
- [schema/ACCEPTANCE_RULES.md](../db/schema/ACCEPTANCE_RULES.md) - Table-level acceptance criteria
- [docs/IMMUTABILITY_POLICY.md](../db/docs/IMMUTABILITY_POLICY.md) - Update/delete restrictions
- [docs/IDEMPOTENCY_STRATEGY.md](../db/docs/IDEMPOTENCY_STRATEGY.md) - Event deduplication
- [docs/AUDIT_TRAIL_DELETION_CONTROLS_VERIFICATION.md](../db/docs/AUDIT_TRAIL_DELETION_CONTROLS_VERIFICATION.md) - Audit cleanup rules
- [docs/](../db/docs/) - 40+ additional governance documents

**Covers**:
- ✓ Which tables exist and why
- ✓ Row-level security (RLS) policies
- ✓ Data immutability constraints
- ✓ Audit trail lifecycle
- ✓ Schema change approval process
- ✓ Migration safety procedures

---

### 2. API Contract Governance
**Location**: `api-contracts/governance/`

**Purpose**: API specification, invariants (ports/headers/auth), vendor integrations, test expectations

**Key Files**:
- [invariants.yaml](../api-contracts/governance/invariants.yaml) - **CRITICAL**: Port assignments, header requirements, authentication scheme
- [canonical-events.yaml](../api-contracts/governance/canonical-events.yaml) - Event taxonomy and validation
- [policies.yaml](../api-contracts/governance/policies.yaml) - API versioning, deprecation, caching
- [integration-maps/](../api-contracts/governance/integration-maps/) - Vendor-specific mappings:
  - [paypal.yaml](../api-contracts/governance/integration-maps/paypal.yaml)
  - [shopify.yaml](../api-contracts/governance/integration-maps/shopify.yaml)
  - [stripe.yaml](../api-contracts/governance/integration-maps/stripe.yaml)
  - [woocommerce.yaml](../api-contracts/governance/integration-maps/woocommerce.yaml)
- [test-expectations/](../api-contracts/governance/test-expectations/) - 7 test cases defining expected endpoint behavior
- [test-payloads/](../api-contracts/governance/test-payloads/) - JSON payloads from each vendor

**Covers**:
- ✓ API port assignments (Auth: 4010, Attribution: 4011, etc.)
- ✓ Required headers (X-Correlation-ID, Authorization, If-None-Match)
- ✓ Authentication scheme (JWT HS256, 1h access + 7d refresh)
- ✓ Caching rules (30s TTL on realtime endpoints)
- ✓ Event contracts (what events are valid)
- ✓ Vendor integrations (how Stripe/Shopify/PayPal events map to canonical events)
- ✓ Expected behaviors (what response should the endpoint return)

---

### 3. Governance Validation Scripts
**Location**: `scripts/governance/`

**Purpose**: Automated enforcement of governance rules in CI/CD

**Key Scripts**:
- `validate_invariants.py` - Enforces api-contracts/governance/invariants.yaml
- `validate_canonical_events.py` - Validates event schema compliance
- `validate_integration_mappings.py` - Checks vendor integration map correctness
- `validate_contract_coverage.py` - Verifies API contract coverage completeness

**Covers**:
- ✓ Port mapping validation
- ✓ Header requirement enforcement
- ✓ Event schema validation
- ✓ Integration mapping correctness
- ✓ Contract completeness checks

---

### 4. Policy Documentation
**Location**: `docs/governance/` and `db/docs/`

**Purpose**: Rationale, procedures, architectural decisions, detailed policy explanations

**Key Docs** (30+ files):
- Decision records (why we chose certain approaches)
- Operational procedures (runbooks for common tasks)
- Privacy and security policies
- Data lifecycle management
- Phase gate criteria and definitions

**Covers**:
- ✓ Architecture decision records (ADRs)
- ✓ Privacy and compliance policies
- ✓ Operational procedures
- ✓ Rationale for governance decisions
- ✓ Historical context and evolution

---

## Cross-Cutting Concerns

### Tenant Isolation & RLS
| Concern | Database Rule | API Rule | Validation |
|---------|---------------|----------|-----------|
| **Policy** | [db/OWNERSHIP.md](../db/OWNERSHIP.md) | [api-contracts/governance/invariants.yaml](../api-contracts/governance/invariants.yaml) | `scripts/governance/validate_invariants.py` |
| **Implementation** | RLS policies on all tenant tables | `tenant_id` in all responses | CI workflow: `contract-enforcement.yml` |

### Event Idempotency
| Concern | Documentation | Implementation | Testing |
|---------|---------------|-----------------|---------|
| **Strategy** | [db/docs/IDEMPOTENCY_STRATEGY.md](../db/docs/IDEMPOTENCY_STRATEGY.md) | [backend/app/ingestion/channel_normalization.py](../backend/app/ingestion/channel_normalization.py) | [api-contracts/governance/test-expectations/](../api-contracts/governance/test-expectations/) |

### PII Controls
| Layer | Location | Role |
|-------|----------|------|
| **Database Enforcement** | [alembic/versions/002_pii_controls/](../alembic/versions/002_pii_controls/) | Triggers prevent PII insertion |
| **API Enforcement** | [backend/app/middleware/pii_stripping.py](../backend/app/middleware/pii_stripping.py) | Middleware redacts PII from responses |
| **Test Validation** | [backend/tests/integration/test_pii_guardrails.py](../backend/tests/integration/test_pii_guardrails.py) | CI verifies PII controls work |
| **Monitoring** | [monitoring/grafana/pii-dashboard.json](../monitoring/grafana/pii-dashboard.json) | Alerts on PII detection |

---

## Quick Reference by Topic

### "How do I add a new webhook vendor (e.g., WooCommerce)?"

1. **Define the contract**: [contracts/webhooks/v1/woocommerce.yaml](../contracts/webhooks/v1/woocommerce.yaml)
2. **Define mapping**: [api-contracts/governance/integration-maps/woocommerce.yaml](../api-contracts/governance/integration-maps/woocommerce.yaml)
3. **Define test expectations**: [api-contracts/governance/test-expectations/woocommerce_*.yaml](../api-contracts/governance/test-expectations/)
4. **Implement handler**: [backend/app/schemas/webhooks_woocommerce.py](../backend/app/schemas/webhooks_woocommerce.py)
5. **Implement ingestion**: Update [backend/app/ingestion/channel_normalization.py](../backend/app/ingestion/channel_normalization.py)
6. **Test**: Add tests to [backend/tests/integration/](../backend/tests/integration/)
7. **Validate**: Run `scripts/governance/validate_integration_mappings.py`

### "What are the API port assignments?"

See: [api-contracts/governance/invariants.yaml](../api-contracts/governance/invariants.yaml) - Port Invariants section

```yaml
Auth API:           port 4010
Attribution API:    port 4011
Reconciliation API: port 4014
Export API:         port 4015
Health API:         port 4016
Shopify Webhooks:   port 4020
Stripe Webhooks:    port 4021
WooCommerce:        port 4022
PayPal Webhooks:    port 4023
```

### "What PII controls are in place?"

1. **Database level**: [alembic/versions/002_pii_controls/](../alembic/versions/002_pii_controls/)
   - Triggers prevent PII columns from being inserted
2. **API level**: [backend/app/middleware/pii_stripping.py](../backend/app/middleware/pii_stripping.py)
   - Middleware redacts PII from all responses
3. **Testing**: [backend/tests/integration/test_pii_guardrails.py](../backend/tests/integration/test_pii_guardrails.py)
   - Validates PII controls work

### "What are the data retention policies?"

See: [db/docs/AUDIT_TRAIL_DELETION_CONTROLS_VERIFICATION.md](../db/docs/AUDIT_TRAIL_DELETION_CONTROLS_VERIFICATION.md)

Policies:
- Analytics data: 90-day retention (then deleted)
- Financial audit data: Permanent retention
- Dead events (resolved): 30-day post-resolution (then deleted)
- Session data: Ephemeral (<=24 hours)

### "How do I make a database schema change?"

1. **Design & review**: [db/schema/ACCEPTANCE_RULES.md](../db/schema/ACCEPTANCE_RULES.md)
2. **Write migration**: [alembic/versions/](../alembic/versions/) (follow template)
3. **Pre-flight checks**: [db/docs/MIGRATION_SAFETY_CHECKLIST.md](../db/docs/MIGRATION_SAFETY_CHECKLIST.md)
4. **Run locally**: `alembic upgrade head`
5. **Test**: `make schema-validate`
6. **CI validation**: `.github/workflows/schema-validation.yml`

### "What are the phase gates?"

See: [db/GOVERNANCE_BASELINE_CHECKLIST.md](../db/GOVERNANCE_BASELINE_CHECKLIST.md)

Current phase: **B0.3** (Database Schema Foundation)
- Core tables created ✓
- PII controls enforced ✓
- RLS policies applied ✓
- Integration mappings complete ✓

### "How do I verify governance compliance?"

Run validation scripts:
```bash
python scripts/governance/validate_invariants.py
python scripts/governance/validate_canonical_events.py
python scripts/governance/validate_integration_mappings.py
python scripts/governance/validate_contract_coverage.py
```

Or run the full CI suite:
```bash
make contract-validate
make schema-validate
pytest tests/contract/
```

---

## Governance Workflow

### For New Features
1. **Define in contract** (api-contracts/openapi/v1/)
2. **Define governance rules** (api-contracts/governance/)
3. **Implement backend** (backend/app/)
4. **Write tests** (backend/tests/)
5. **Run validation** (scripts/governance/)
6. **Merge to main** (CI enforces all checks)

### For Schema Changes
1. **Design the change** (db/schema/)
2. **Write migration** (alembic/versions/)
3. **Write tests** (db/tests/)
4. **Run pre-flight checks** (db/docs/MIGRATION_SAFETY_CHECKLIST.md)
5. **Test locally** (make schema-validate)
6. **Merge and run** (CI executes migrations)

### For Integration Changes
1. **Study vendor documentation** (api-contracts/governance/test-payloads/)
2. **Define mapping** (api-contracts/governance/integration-maps/)
3. **Write test cases** (api-contracts/governance/test-expectations/)
4. **Implement handler** (backend/app/schemas/webhooks_*.py)
5. **Validate** (scripts/governance/validate_integration_mappings.py)
6. **Test** (pytest backend/tests/)

---

## How to Use This Index

**First time here?** Start with entry point for your role (see top of this document)

**Need to find something specific?** Use "Quick Reference by Topic" section

**Want the deep dive?** Follow links to specific governance layer documentation

**Something not listed?** Check [db/docs/](../db/docs/) or [docs/governance/](../docs/governance/) directly

---

**Last Updated**: 2025-12-07
**Maintained By**: Backend Engineering Lead
**Governance Framework**: Contract-first, multi-layered, CI-enforced
