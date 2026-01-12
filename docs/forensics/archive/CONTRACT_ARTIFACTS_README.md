# Contract Artifacts Operationalization - Quick Start Guide

This guide explains how to use the newly operationalized contract artifacts system (mocks, tests, docs).

## What Changed?

### Before
- ❌ Mocks bound to source files (contracts/*/v1/*.yaml)
- ❌ Docker Compose (incompatible with Replit)
- ❌ No contract integrity tests
- ❌ Manual documentation
- ❌ No CI enforcement

### After
- ✅ Mocks bound to validated bundles (api-contracts/dist/openapi/v1/*.bundled.yaml)
- ✅ Replit-native Prism CLI subprocesses
- ✅ Contract integrity tests (Schmidt's Phase B)
- ✅ Automated documentation with traceability
- ✅ CI hard gates with failure diagnostics

---

## Quick Start

### 1. Bundle Contracts (Required First)

```bash
bash scripts/contracts/bundle.sh
```

This creates validated bundles in `api-contracts/dist/openapi/v1/*.bundled.yaml`.

### 2. Start Mock Servers

```bash
bash scripts/start-mocks.sh
```

This starts 3 primary mocks:
- Auth: http://localhost:4010
- Attribution: http://localhost:4011
- Health: http://localhost:4012

### 3. Run Contract Tests

```bash
# Run both integrity and provider tests
make contract-full

# Or run separately:
make contract-integrity   # Mocks vs contracts
make contract-provider    # Implementation vs contracts
```

### 4. Build Documentation

```bash
make docs-build
make docs-validate
make docs-view  # Opens in browser
```

Documentation is generated at `api-contracts/dist/docs/v1/`.

---

## Mock Server Management

### Primary Mocks (Auto-Start)

The following mocks start automatically:
- **auth** (port 4010): Authentication API
- **attribution** (port 4011): Attribution API
- **health** (port 4012): Health API

### On-Demand Mocks

Switch to other APIs as needed:

```bash
# Switch to reconciliation
bash scripts/switch-mock.sh reconciliation

# Switch to export
bash scripts/switch-mock.sh export

# Switch to webhooks
bash scripts/switch-mock.sh shopify
bash scripts/switch-mock.sh woocommerce
bash scripts/switch-mock.sh stripe
bash scripts/switch-mock.sh paypal
```

On-demand mocks run on port 4013.

### Stop Mocks

```bash
bash scripts/stop-mocks.sh
```

### Restart Mocks

```bash
bash scripts/restart-mocks.sh
```

---

## Testing

### Test Sequence (Schmidt's Causal Chain)

Tests run in this order:

1. **Integrity Tests** (Phase B): Mocks vs Contracts
   - Validates contract examples are valid against schemas
   - Proves contracts are internally consistent
   - If fails: Fix the contract

2. **Provider Tests** (Phase C): Implementation vs Contracts
   - Validates FastAPI implementation matches contracts
   - Proves implementation conforms to validated contracts
   - If fails: Fix the implementation

### Running Tests

```bash
# Full pipeline (recommended)
make contract-full

# Individual test suites
make contract-integrity   # Run integrity tests
make contract-provider    # Run provider tests

# Specific domains
cd tests/contract
pytest test_mock_integrity.py::test_mock_integrity[auth] -v
pytest test_contract_semantics.py::test_auth_login_happy_path -v
```

### Understanding Test Failures

| Integrity | Provider | Diagnosis | Action |
|-----------|----------|-----------|--------|
| ✓ Pass | ✓ Pass | All correct | No action |
| ✓ Pass | ✗ Fail | Implementation divergence | Fix FastAPI code |
| ✗ Fail | ✓ Pass | Impossible state | Contract has invalid examples |
| ✗ Fail | ✗ Fail | Contract issue | Fix contract first |

---

## Documentation

### Building Docs

```bash
# Build all documentation
make docs-build

# Validate generated docs
make docs-validate

# View in browser
make docs-view
```

### Documentation Structure

```
api-contracts/dist/docs/v1/
├── index.html              # Main index page
├── auth.html               # Authentication API docs
├── attribution.html        # Attribution API docs
├── reconciliation.html     # Reconciliation API docs
├── export.html             # Export API docs
├── health.html             # Health API docs
├── webhooks_shopify.html   # Shopify webhooks docs
├── webhooks_woocommerce.html
├── webhooks_stripe.html
└── webhooks_paypal.html
```

Each HTML file contains traceability metadata:
- Git commit SHA
- Build timestamp
- Source bundle path
- Generator version

---

## CI/CD Integration

### GitHub Actions Workflow

The `contract-artifacts` workflow runs automatically on:
- Push to `main` or `develop`
- Pull requests
- Changes to contracts, backend API, or scripts

### Jobs

1. **contract-bundling**: Bundle and validate contracts
2. **contract-integrity-tests**: Test mocks vs contracts
3. **contract-provider-tests**: Test implementation vs contracts
4. **contract-docs**: Build and validate documentation

All jobs must pass for PR approval.

### Failure Diagnostics

If CI fails, check the job output:

- **Bundling failed**: Invalid OpenAPI syntax
  - Action: Fix YAML syntax errors

- **Integrity failed**: Contract examples violate schemas
  - Action: Fix examples in source YAML files

- **Provider failed**: Implementation diverges from contracts
  - Action: Fix FastAPI code to match contracts

- **Docs failed**: Unable to build or validate docs
  - Action: Check Redocly errors

---

## Troubleshooting

### Mocks Won't Start

```bash
# Check if bundles exist
ls -la api-contracts/dist/openapi/v1/*.bundled.yaml

# If missing, bundle first
bash scripts/contracts/bundle.sh

# Check if Prism is installed
prism --version

# If not installed
npm install -g @stoplight/prism-cli
```

### Port Already in Use

```bash
# Stop existing mocks
bash scripts/stop-mocks.sh

# Check for orphaned processes
ps aux | grep prism

# Kill manually if needed
kill <PID>
```

### Tests Failing

```bash
# Ensure mocks are running
bash scripts/start-mocks.sh

# Check mock health
curl http://localhost:4010/api/auth/login -X POST -H "Content-Type: application/json" -d '{"email":"test","password":"test"}'
curl http://localhost:4011/api/attribution/revenue/realtime -H "Authorization: Bearer mock"
curl http://localhost:4012/api/health

# Re-bundle if contracts changed
bash scripts/contracts/bundle.sh
bash scripts/restart-mocks.sh
```

### Documentation Won't Build

```bash
# Check if Redocly CLI is installed
redocly --version

# If not installed
npm install -g @redocly/cli

# Ensure bundles exist
bash scripts/contracts/bundle.sh

# Try building docs
bash scripts/contracts/build_docs.sh
```

---

## Domain Mapping

View the domain → bundle → port mapping:

```bash
python scripts/contracts/print_domain_map.py

# Or use Makefile
make domain-map
```

Sample output:
```
[OK]       auth                      -> Port 4010 [PRIMARY  ]
[OK]       attribution               -> Port 4011 [PRIMARY  ]
[OK]       health                    -> Port 4012 [PRIMARY  ]
[OK]       reconciliation            -> Port 4013 [ON-DEMAND]
...
```

---

## Migration Notes

### From Docker Compose

The old `docker-compose.yml` has been deprecated and renamed to `docker-compose.yml.deprecated`.

**Old command:**
```bash
docker-compose up
```

**New command:**
```bash
bash scripts/start-mocks.sh
```

**Why the change?**
- Replit doesn't support Docker
- Subprocess-based approach is more flexible
- Port constraints enforced (max 3 concurrent)
- Binds to validated bundles, not source files

---

## Makefile Commands

```bash
make contract-full          # Run full pipeline
make contract-integrity     # Run integrity tests
make contract-provider      # Run provider tests
make docs-build            # Build documentation
make docs-validate         # Validate documentation
make docs-view             # Open docs in browser
make domain-map            # Show domain mapping
make mocks-start           # Start mock servers
make mocks-stop            # Stop mock servers
make mocks-restart         # Restart mock servers
make mocks-switch DOMAIN=<name>  # Switch on-demand mock
```

---

## Further Reading

- **Implementation Details**: See `IMPLEMENTATION_COMPLETE.md`
- **Test Documentation**: See `tests/contract/README.md`
- **CI Workflow**: See `.github/workflows/contract-artifacts.yml`
- **Mock Registry**: See `scripts/contracts/mock_registry.json`

---

## Support

If you encounter issues:

1. Check this README
2. Review `IMPLEMENTATION_COMPLETE.md`
3. Examine CI job logs
4. Check mock server logs in `/tmp/prism-*.log`
5. Verify bundles exist and are valid

**Remember the sequence:** Bundle → Integrity → Provider → Docs

Each step depends on the previous one. Always start with bundling.



