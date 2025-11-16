# Contributing to SKELDIR 2.0 Monorepo

Thank you for your interest in contributing to SKELDIR 2.0! This guide outlines the monorepo contribution workflow.

## Monorepo Overview

This is a monorepo containing:
- **Contracts**: OpenAPI 3.1 specifications (`contracts/`)
- **Backend**: FastAPI application (`backend/`)
- **Frontend**: Replit UI (`frontend/`)
- **Shared Infrastructure**: Documentation, scripts, tests

All components are versioned atomically via single commit hashes.

## Contract-First Development Workflow

SKELDIR follows a **contract-first** approach:

1. **Define Contract**: Create/update OpenAPI spec in `contracts/{domain}/v1/` (e.g., `contracts/attribution/v1/attribution.yaml`)
2. **Validate Contract**: Run `make contracts-validate`
3. **Generate Models**: Run `make models-generate` to create Pydantic models
4. **Implement Backend**: Implement endpoints in `backend/app/`
5. **Update Frontend**: Update frontend SDK and UI
6. **Test Integration**: Run integration tests

## Development Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- Git

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd skeldir-2.0

# Install root dependencies (if package.json exists)
npm install

# Setup backend
cd backend
pip install -r requirements.txt
alembic upgrade head

# Setup frontend
cd ../frontend
npm install
```

## Making Changes

### Contract Changes

1. Edit OpenAPI spec in `contracts/{domain}/v1/` (e.g., `contracts/attribution/v1/attribution.yaml`)
2. Validate: `make contracts-validate`
3. Check for breaking changes: CI will run `oasdiff breaking`
4. Update baseline if major version bump

### Backend Changes

1. Update contract first (if needed)
2. Generate models: `make models-generate`
3. Implement in `backend/app/`
4. Write tests in `backend/tests/`
5. Run tests: `cd backend && pytest`

### Frontend Changes

1. Update contract first (if needed)
2. Regenerate SDK (if contracts changed)
3. Update UI in `frontend/src/`
4. Run tests: `cd frontend && npm test`

## Testing

### Unit Tests

- Backend: `cd backend && pytest`
- Frontend: `cd frontend && npm test`

### Integration Tests

```bash
# Start mock servers
make mocks-start

# Run integration tests
make tests-integration
```

## Pull Request Process

1. Create feature branch from `main`
2. Make changes following contract-first workflow
3. Ensure all tests pass
4. Update documentation if needed
5. Submit PR with clear description

### PR Requirements

- All tests pass (unit + integration)
- Contracts validate successfully
- No breaking changes (unless major version bump)
- Documentation updated if needed

## Code Style

- **Python**: Follow PEP 8, use `black` for formatting
- **TypeScript/JavaScript**: Follow ESLint rules
- **OpenAPI**: Follow existing contract structure

## Commit Messages

Use conventional commits:
- `feat(contracts): add new endpoint`
- `fix(backend): resolve authentication issue`
- `docs: update monorepo structure guide`

## Questions?

- Review [monorepo structure](docs/MONOREPO_STRUCTURE.md)
- Check [development workflow](docs/DEVELOPMENT_WORKFLOW.md)
- See [contract documentation](contracts/README.md)

