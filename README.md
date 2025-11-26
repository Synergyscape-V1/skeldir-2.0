# SKELDIR 2.0 Monorepo

**Unified repository for Skeldir 2.0 Attribution Intelligence platform**

> **Note**: This is a monorepo containing contracts, backend, frontend, and shared infrastructure. All components are versioned atomically via single commit hashes.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

This monorepo contains the complete Skeldir 2.0 Attribution Intelligence platform, following a **contract-first** development approach with atomic versioning. All components (contracts, backend, frontend) are versioned together in a single repository, enabling:

> **Note**: This monorepo includes the complete content from the original [`skeldir-api-contracts`](https://github.com/Muk223/skeldir-api-contracts) repository directly in the `contracts/` directory. The original repository structure is preserved, and all contract development occurs in this monorepo for atomic versioning with backend and frontend code.

- **Atomic Versioning**: Single commit hash versions all components simultaneously
- **CI/CD Simplification**: Single git checkout for all validation and testing
- **Contract-Driven Development**: OpenAPI contracts serve as immutable source of truth
- **Integration Testing**: End-to-end tests against Prism mock servers
- **Prevented Contract Drift**: Architecturally impossible for frontend/backend to be out of sync

## Repository Structure

```
.
├── backend/          # FastAPI application (modular monolith)
│   ├── app/          # Application code (ingestion, attribution, auth, webhooks)
│   ├── db/           # Database migrations, seeds, snapshots
│   ├── alembic/      # Alembic configuration
│   └── tests/        # Backend unit tests
├── frontend/         # Replit UI (to be migrated)
│   ├── src/          # Frontend source code
│   └── public/       # Static assets
├── contracts/        # OpenAPI 3.1.0 contract specifications (includes original skeldir-api-contracts content)
│   ├── openapi/      # Original repository structure preserved
│   │   └── v1/       # Version 1 API contracts
│   └── baselines/    # Frozen baselines for breaking change detection
├── api-contracts/    # Legacy contracts directory (preserved for reference)
├── docs/             # Shared documentation
│   └── database/     # Database governance documentation
├── scripts/          # Shared utility scripts
├── tests/            # Integration tests (Playwright)
└── .github/          # CI/CD workflows
```

## Quick Start

### Prerequisites

- Node.js 20+ (for OpenAPI validation, documentation, and frontend)
- Python 3.11+ (for backend and Pydantic model generation)
- Docker & Docker Compose (for mock servers)
- Git

### Contract Validation

```bash
# Validate all OpenAPI contracts
make contracts-validate
# or
npm run contracts:validate
```

### Mock Servers

Start Prism mock servers for frontend development:

```bash
# Start all mock servers
make mocks-start
# or
./scripts/start-mocks.sh

# Stop all mock servers
make mocks-stop
# or
./scripts/stop-mocks.sh
```

**Service URLs:**
- Auth: `http://localhost:4010`
- Attribution: `http://localhost:4011`
- Reconciliation: `http://localhost:4012`
- Export: `http://localhost:4013`
- Health: `http://localhost:4014`
- Webhooks: `http://localhost:4015-4018`

### Integration Tests

Run Playwright integration tests against mock servers:

```bash
# Run integration tests
make tests-integration
# or
npm test
```

### Backend Development

```bash
cd backend
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Run backend tests
pytest
```

### Frontend Development

```bash
cd frontend
# Install dependencies
npm install

# Start development server
npm start
```

## Documentation

- **[Monorepo Structure](docs/MONOREPO_STRUCTURE.md)**: Detailed folder organization
- **[Development Workflow](docs/DEVELOPMENT_WORKFLOW.md)**: Contract-first workflow in monorepo context
- **[API Contracts](contracts/README.md)**: OpenAPI contract documentation
- **[Contributing](docs/CONTRIBUTING.md)**: Contribution guidelines
- **[CI/CD](docs/CI_CD.md)**: Continuous integration and deployment
- **[Database](docs/database/)**: Database governance and migration guides

## Versioning

All components follow [Semantic Versioning](https://semver.org/) and are versioned atomically:

- **Single Version Number**: One version number applies to contracts, backend, and frontend
- **Single Commit Hash**: Each commit versions all components simultaneously
- **Breaking Changes**: Require major version bump and affect all components

Current version: **1.0.0**

## CI/CD

The monorepo uses a unified CI/CD pipeline that:

- Validates OpenAPI contracts
- Runs backend unit tests
- Runs frontend tests
- Executes integration tests (Playwright)
- Detects breaking changes
- Generates Pydantic models from contracts

All validation occurs in a single GitHub Actions workflow with a single git checkout.

## Contract-First Development

1. **Define Contract**: Create/update OpenAPI spec in `contracts/openapi/v1/`
2. **Generate Models**: Run `make models-generate` to create Pydantic models
3. **Implement Backend**: Implement endpoints in `backend/app/`
4. **Update Frontend**: Update frontend SDK and UI
5. **Test Integration**: Run integration tests against mock servers

## Privacy & Security

- **No PII**: All webhook endpoints include explicit PII-stripping statements
- **Session-scoped**: No cross-session tracking (30-minute inactivity timeout)
- **Tenant isolation**: Enforced via `tenant_id` in all authenticated responses
- **HMAC validation**: Required for all webhook endpoints

See [SECURITY.md](SECURITY.md) for security policy and [PRIVACY-NOTES.md](PRIVACY-NOTES.md) for detailed privacy constraints.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For questions:
- Review [architecture guide](.cursor/rules) for design decisions
- Check [contract migration template](contracts/MIGRATION_TEMPLATE.md) for breaking change documentation
- See [monorepo structure guide](docs/MONOREPO_STRUCTURE.md) for folder organization
# Test CI with line 129 fixed
