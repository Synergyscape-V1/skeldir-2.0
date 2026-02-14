# Validation Infrastructure Setup

## Overview

This document describes the contract validation, mock orchestration, and evidence collection infrastructure promoted from the Replit validation environment to the main backend repository.

**Promotion Date**: November 24, 2025  
**Source Environment**: Replit AI Validation Environment  
**Target Repository**: https://github.com/Muk223/skeldir-2.0

## Assurance Statement

✅ **NO business logic, data models, or core operational scripts were modified or replaced.**

- All new validation infrastructure is **strictly additive**
- Existing scripts in `/scripts/` directory remain unchanged
- Existing business logic in `/backend/` directory remains unchanged
- All changes are contained in dedicated `/scripts/validation/` subdirectory

## Promoted Assets

### 1. Mock Server Orchestration
- **Location**: `/scripts/validation/start-mocks.sh` (platform-agnostic)
- **Original Source**: `scripts/start-mocks-replit.sh` (Replit-specific)
- **Purpose**: Launch all 9 Prism CLI mock servers in parallel for contract validation
- **Ports**: 4010-4018 (Auth, Attribution, Reconciliation, Export, Health, Webhooks)
- **Key Changes**: Removed Replit-specific logic, added environment detection for cross-platform compatibility

### 2. Breaking Change Detection
- **Location**: `/scripts/validation/detect-breaking-changes.sh`
- **Purpose**: Compare current contract versions against v1.0.0 baselines to detect breaking changes
- **Baseline Location**: `/contracts/baselines/v1.0.0/`
- **CI Integration**: Can be integrated into GitHub Actions workflow

### 3. Contract Baseline Structure
- **Location**: `/contracts/baselines/v1.0.0/`
- **Files**:
  - `auth.yaml` - Authentication service contract baseline
  - `attribution.yaml` - Attribution service contract baseline
  - `export.yaml` - Export service contract baseline
  - `health.yaml` - Health service contract baseline
  - `reconciliation.yaml` - Reconciliation service contract baseline
  - `webhooks/shopify.yaml` - Shopify webhook contract baseline
  - `webhooks/stripe.yaml` - Stripe webhook contract baseline
  - `webhooks/paypal.yaml` - PayPal webhook contract baseline
  - `webhooks/woocommerce.yaml` - WooCommerce webhook contract baseline

### 4. Model Generation
- **Location**: `/scripts/validation/generate-models.sh` (platform-agnostic)
- **Purpose**: Generate Pydantic v2 models from OpenAPI 3.1.0 contracts
- **Output Directory**: `/backend/app/schemas/`
- **Requirement**: JDK17 (for OpenAPI generator CLI)

### 5. Documentation and Support Scripts
- `/scripts/validation/README.md` - Detailed validation infrastructure documentation
- `/logs/` - Template directories for logs (not committed, see .gitignore)
- `/logs/http-evidence/` - HTTP request/response evidence (template only)
- `/logs/validation/` - Validation execution logs (template only)
- `/logs/breaking-changes/` - Breaking change detection reports (template only)

## Development Dependencies

Add these to `package.json` devDependencies:

```json
{
  "devDependencies": {
    "@openapitools/openapi-generator-cli": "^2.25.2",
    "@stoplight/prism-cli": "^5.14.2",
    "js-yaml": "^4.1.0"
  }
}
```

## Setup Instructions

### Prerequisites
- Node.js 18+
- JDK 17 (required for @openapitools/openapi-generator-cli)
- Bash 4.0+ (or compatible shell)
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Verify mock server CLI is available
npx prism --version

# Verify model generator is available
npx openapi-generator-cli --version
```

### Running Validation

#### Start Mock Servers
```bash
bash scripts/validation/start-mocks.sh
```

#### Generate Models
```bash
bash scripts/validation/generate-models.sh
```

#### Detect Breaking Changes
```bash
bash scripts/validation/detect-breaking-changes.sh
```

#### Run All Validation via NPM Scripts
```bash
# NPM scripts defined in package.json
npm run contracts:validate      # Validate contract structure
npm run models:generate         # Generate Pydantic models
npm run mocks:start             # Start mock servers
npm run changes:detect          # Detect breaking changes
```

## Directory Structure

```
skeldir-2.0/
├── contracts/
│   ├── baselines/
│   │   └── v1.0.0/              # Contract baseline snapshots
│   │       ├── auth.yaml
│   │       ├── attribution.yaml
│   │       ├── export.yaml
│   │       ├── health.yaml
│   │       ├── reconciliation.yaml
│   │       └── webhooks/
│   │           ├── shopify.yaml
│   │           ├── stripe.yaml
│   │           ├── paypal.yaml
│   │           └── woocommerce.yaml
│   └── [existing contracts...]  # Unchanged
├── scripts/
│   ├── validation/               # NEW: Validation infrastructure
│   │   ├── start-mocks.sh
│   │   ├── detect-breaking-changes.sh
│   │   ├── generate-models.sh
│   │   └── README.md
│   └── [existing scripts...]     # Unchanged
├── logs/                          # Template directories (not committed)
│   ├── http-evidence/
│   ├── validation/
│   └── breaking-changes/
├── .gitignore                     # Updated to exclude logs/
└── package.json                   # Updated with devDependencies
```

## Platform Independence

All scripts have been refactored for platform independence:

- ✅ Removed Replit workspace references
- ✅ Added environment detection (Linux, macOS, Windows with WSL)
- ✅ Use standard POSIX shell commands
- ✅ Portable path handling (no hardcoded `/home/replit/` paths)
- ✅ Configuration via environment variables where appropriate

## Validation Workflow

### Pre-Deployment Validation

When code is merged to main, this workflow runs:

```
1. Start mock servers (validates contract structure)
2. Run health checks (validates mock server responses)
3. Generate models (validates model generation)
4. Detect breaking changes (validates contract versioning)
5. Generate evidence report (logs to /logs/)
```

### Manual Testing

Developers can run individual validation steps locally using the scripts or NPM commands.

## Evidence Collection

Validation evidence is collected in `/logs/` directories:

- `logs/http-evidence/` - HTTP request/response traces
- `logs/validation/` - Validation execution logs
- `logs/breaking-changes/` - Breaking change detection reports

**Note**: These directories are template-only and log files are excluded from git commits via `.gitignore`.

## Maintenance and Support

- **Maintainer**: SKELDIR Development Team
- **Issue Reports**: Create issues in the GitHub repository
- **Documentation**: See `/scripts/validation/README.md` for detailed information
- **Questions**: Refer to DELIVERY_PROOF.md in Replit validation environment for evidence of completed deliverables

## Changelist

This promotion includes:

✅ Infrastructure scripts (platform-agnostic)  
✅ Contract baseline files (v1.0.0)  
✅ Development dependency declarations  
✅ Comprehensive documentation  
✅ .gitignore updates for logs/  
✅ NPM script definitions  
❌ NO changes to existing business logic  
❌ NO changes to existing data models  
❌ NO changes to existing operational scripts  

## Related Documentation

- See `VALIDATION_INFRASTRUCTURE_SETUP.md` for this setup guide
- See `/scripts/validation/README.md` for detailed validation infrastructure documentation
- See DELIVERY_PROOF.md (Replit environment) for evidence of completed B0.1 deliverables
- See REPLIT_BASELINE_VALIDATION.md (Replit environment) for validation baseline details
