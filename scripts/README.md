# Scripts Directory

**Organization and usage guide for SKELDIR 2.0 operational scripts**

---

## Quick Navigation

| Need | Script | Command |
|------|--------|---------|
| **Start mock servers** | `start-mocks.sh` | `make mock-start` or `./scripts/start-mocks.sh` |
| **Health check mocks** | `health-check-mocks.sh` | `./scripts/health-check-mocks.sh` |
| **Validate contracts** | `contracts/check.sh` | `make contract-validate` |
| **Validate schema authority** | `schema/assert_canonical_schema.py` | `python scripts/schema/assert_canonical_schema.py --mode auto` |
| **Generate models** | `generate-models.sh` | `make model-generate` |
| **Run phase gate** | `phase_gates/run_gate.py` | `python scripts/phase_gates/run_gate.py --phase B0.3` |

---

## Directory Organization

### `contracts/` - API Contract Management
**Purpose**: Bundle, validate, and maintain OpenAPI specifications

**Usage**:
```bash
# Bundle all contracts into single specs
scripts/contracts/bundle.sh

# Full validation pipeline (bundles, lints, validates)
scripts/contracts/check.sh

# Generate Pydantic models from contracts
scripts/generate-models.sh
```

**Key Files**:
- `bundle.sh` - Combines multiple YAML files → single OpenAPI spec
- `check.sh` - Main validation pipeline (calls other validators)
- `check_*.py` - Specific validators (no_orphaned_refs, coverage, etc.)
- `dump_*.py` - Debug utilities (dump routes, schemas, endpoints)
- `print_*.py` - Route classification (implemented vs. stubbed)
- `validate_*.py` - Schema validators (invariants, canonical events)
- `schema/assert_canonical_schema.py` - Deterministic migration->dump->diff authority gate
- `identity/assert_runtime_identity.py` - Runtime vs migration DB identity parity gate
- `entrypoints.json` - Route mapping: /path → implementation
- `mock_registry.json` - Mock endpoint registry

---

### `governance/` - Governance Rule Validation
**Purpose**: Enforce architectural governance rules in CI/CD

**Usage**:
```bash
# Validate API invariants (ports, headers, auth)
python scripts/governance/validate_invariants.py

# Validate event taxonomy
python scripts/governance/validate_canonical_events.py

# Validate vendor integration mappings
python scripts/governance/validate_integration_mappings.py

# Validate contract coverage
python scripts/governance/validate_contract_coverage.py
```

**Key Scripts**:
- `validate_invariants.py` - Port, header, auth validation
- `validate_canonical_events.py` - Event schema validation
- `validate_integration_mappings.py` - Vendor mapping validation
- `validate_contract_coverage.py` - Coverage manifest validation

---

### `phase_gates/` - Release Phase Validation
**Purpose**: Enforce phase gate criteria before merging/releasing

**Usage**:
```bash
# Run phase gate for current phase (B0.3)
python scripts/phase_gates/run_gate.py --phase B0.3

# Or via Makefile
make phase-gate-b0.3
```

**Key Scripts**:
- `run_gate.py` - Main gate executor (checks acceptance criteria)
- `b0_1_gate.py` - B0.1 specific checks (contracts defined)
- `b0_2_gate.py` - B0.2 specific checks (frontend ready)
- `b0_3_gate.py` - B0.3 specific checks (database complete)
- `record_ack.py` - Records phase completion
- `write_empirical_chain.py` - Documents evidence

---

### `mocks/` - Mock Server Utilities
**Purpose**: Manage local mock servers for development and testing

**Usage**:
```bash
# Start all 9 API mock servers (CANONICAL)
make mock-start
# or
./scripts/start-mocks.sh

# Health check
./scripts/health-check-mocks.sh

# View logs
tail -f /tmp/skeldir-mocks/prism_4010.log
```

**Key Scripts**:
- **`start-mocks.sh`** - **CANONICAL** mock server startup (Prism CLI, all 9 APIs)
  - Starts: Auth (4010), Attribution (4011), Reconciliation (4014), Export (4015), Health (4016)
  - Plus: Shopify (4020), Stripe (4021), WooCommerce (4022), PayPal (4023)
  - Configuration: Reads from api-contracts/openapi/v1/*.yaml
- `start-mocks-old-mockoon.sh` - Deprecated Mockoon version (5 APIs only)
- `health-check-mocks.sh` - Validates all mock endpoints are responding
- `stop-mocks-prism.sh` - Shutdown mock servers

---

### `database/` - Database Utilities
**Purpose**: Database-specific tools and monitoring

**Key Scripts**:
- `run_query_performance.py` - Profile query latency and identify slow queries

---

### `ci/` - CI/CD Helper Scripts
**Purpose**: Utilities used by GitHub Actions workflows

**Note**: Typically not run manually; called by workflows in `.github/workflows/`

---

## Naming Convention

**Consistency Rule**:
- **Shell scripts**: `kebab-case.sh`
- **Python scripts**: `snake_case.py`

**Examples**:
```
✓ start-mocks.sh              (shell, kebab-case)
✓ validate_schema_compliance.py (python, snake_case)
✓ check-mock-health.sh        (shell, kebab-case)
✓ validate_invariants.py      (python, snake_case)
```

---

## Running Scripts

### Via Makefile (Recommended for Common Tasks)
```bash
make mock-start           # Start mocks
make test-backend         # Run backend tests
make contract-validate    # Validate contracts
make schema-validate      # Validate database schema
make phase-gate-b0.3      # Run B0.3 phase gate
```

### Direct Execution
```bash
# From repository root:
./scripts/start-mocks.sh
python scripts/governance/validate_invariants.py
bash scripts/contracts/check.sh
```

### From CI/CD
Scripts are called directly in `.github/workflows/*.yml` files:
```yaml
- name: Validate schema compliance
  run: python scripts/validate-schema-compliance.py
```

---

## Script Categories by Use

### Development/Local Testing
- `start-mocks.sh` - Local mock servers
- `health-check-mocks.sh` - Verify mock health
- `generate-models.sh` - Generate Pydantic models

### Continuous Integration (CI)
- `contracts/check.sh` - Contract validation
- `governance/validate_*.py` - Governance checks
- `validate-schema-compliance.py` - Database schema validation
- `phase_gates/run_gate.py` - Phase gate enforcement

### One-Off Utilities/Analysis
- `contracts/dump_*.py` - Debug/introspection
- `contracts/print_*.py` - Route listing/classification
- `database/run_query_performance.py` - Performance analysis

### Operations/Deployment
- `validate-migration.sh` - Pre-migration safety checks
- `phase_gates/record_ack.py` - Phase completion acknowledgment

---

## Common Tasks

### "How do I start developing locally?"

```bash
# Terminal 1: Start mock servers
make mock-start

# Terminal 2: Run tests
make test-backend

# Terminal 3: Start frontend
cd frontend && npm run dev
```

### "How do I validate my changes?"

```bash
# Run all local validations
make contract-validate      # API contracts
make schema-validate        # Database schema
make test-backend           # Backend tests
pytest tests/contract/      # Contract integration tests
```

### "How do I deploy to the next phase?"

```bash
# Check phase requirements
python scripts/phase_gates/run_gate.py --phase B0.4

# If gate passes, merge and deploy
# If gate fails, fix issues and retry
```

### "How do I debug why a mock endpoint isn't working?"

```bash
# Check mock health
./scripts/health-check-mocks.sh

# View logs for specific port
tail -f /tmp/skeldir-mocks/prism_4010.log

# Verify contract matches mock
python scripts/governance/validate_invariants.py
```

---

## Script Dependencies

```
Makefile
├── scripts/start-mocks.sh           (uses Prism CLI)
├── scripts/contracts/check.sh       (uses Spectral, oasdiff)
├── scripts/generate-models.sh       (uses datamodel-code-generator)
├── scripts/validate-schema-compliance.py
├── scripts/phase_gates/run_gate.py
└── [CI workflows call these directly]
```

**Prerequisites**:
- Node.js 20+ (for Prism, bundler)
- Python 3.11+ (for validators)
- PostgreSQL (for schema validation)

---

## Environment Variables

Scripts respect these environment variables:

```bash
CONTRACT_DIR          # Location of OpenAPI specs (default: api-contracts/openapi/v1)
DATABASE_URL          # PostgreSQL connection (default: localhost/skeldir_test)
VITE_*                # Frontend environment variables (loaded by frontend, not scripts)
```

---

## Troubleshooting

### Mock servers won't start
```bash
# Check if ports are already in use
lsof -i :4010  # Check port 4010

# Kill existing processes
pkill -f prism

# Try starting again
./scripts/start-mocks.sh
```

### Schema validation fails
```bash
# Run with verbose output
python scripts/validate-schema-compliance.py

# Check if database is running
psql $DATABASE_URL -c "SELECT version();"

# Check current schema
alembic current
```

### Contract validation fails
```bash
# Run bundler manually
bash scripts/contracts/bundle.sh

# Run linter
npx @stoplight/spectral-cli lint api-contracts/openapi/v1/*.yaml

# Run semantic validation
python scripts/contracts/check_breaking_changes.py
```

---

## Contributing New Scripts

When adding a script:

1. **Choose correct directory** (contracts/, governance/, phase_gates/, etc.)
2. **Follow naming convention** (kebab-case.sh for shell, snake_case.py for Python)
3. **Add header comment** explaining purpose, usage, requirements
4. **Document in this README** (add to appropriate section)
5. **Add to Makefile** if it's a common task
6. **Add to CI** if it should validate PRs

---

## Related Documentation

- **[GOVERNANCE_INDEX.md](../docs/GOVERNANCE_INDEX.md)** - Governance rules location
- **[PHASE_MIGRATION_MAPPING.md](../docs/PHASE_MIGRATION_MAPPING.md)** - Phase gate structure
- **[Makefile](../Makefile)** - Build target definitions
- **[.github/workflows/](../.github/workflows/)** - CI/CD automation

---

**Last Updated**: 2025-12-07
**Maintained By**: Backend Engineering Lead
**Primary Interface**: `make` targets + direct execution
