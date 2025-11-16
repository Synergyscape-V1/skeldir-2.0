# API Evolution Strategy

**Purpose**: Document API versioning, backward compatibility, and evolution policies.

**Last Updated**: 2025-11-16

## Versioning Policy

### Semantic Versioning

**Format**: `v{MAJOR}.{MINOR}.{PATCH}`

**Current Version**: `v1.0.0`

### Version Bump Rules

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| **Breaking Change** | MAJOR (v1 → v2) | Removed endpoint, changed response schema, changed required field |
| **Non-Breaking Addition** | MINOR (v1.0 → v1.1) | New endpoint, new optional field, new optional parameter |
| **Documentation Only** | PATCH (v1.0.0 → v1.0.1) | Updated descriptions, examples, documentation |

### Breaking Change Definition

A change is **breaking** if it:
1. **Removes** an endpoint or operation
2. **Changes** response schema (removes field, changes type, makes optional field required)
3. **Changes** request schema (removes optional field, changes type, makes optional field required)
4. **Changes** parameter types or removes parameters
5. **Changes** authentication/authorization requirements

### Non-Breaking Change Definition

A change is **non-breaking** if it:
1. **Adds** new endpoints or operations
2. **Adds** new optional fields to request/response schemas
3. **Adds** new optional parameters
4. **Expands** enum values (existing values remain valid)
5. **Updates** documentation, examples, descriptions

## Baseline Strategy

### Baseline Storage

**Location**: `contracts/{domain}/baselines/v{MAJOR}.{MINOR}.{PATCH}/`

**Purpose**: Immutable snapshots of contract versions for:
- Breaking change detection
- Client generation for specific versions
- Historical reference

### Baseline Creation

**When to Create Baseline**:
- After major version release (v1.0.0, v2.0.0)
- Before making breaking changes
- After contract stabilization

**Process**:
1. Copy active contract to baseline directory
2. Commit baseline to version control
3. Tag baseline with version number

## Breaking Change Detection

### Automated Detection

**Tool**: `scripts/detect-breaking-changes.sh`

**Method**: Compare active contracts (`contracts/{domain}/v1/`) against baselines (`contracts/{domain}/baselines/v1.0.0/`)

**CI Integration**: `.github/workflows/ci.yml` - `validate-contracts` job

**Detection Criteria**:
- Removed endpoints
- Changed response schemas
- Changed required fields
- Changed parameter types

### Manual Review Process

**When Breaking Changes Detected**:
1. **Assess Impact**: Determine affected clients and consumers
2. **Version Decision**: 
   - If breaking change required → Bump to v2.0.0
   - If breaking change can be avoided → Refactor to non-breaking
3. **Migration Plan**: Document migration path for consumers
4. **Approval**: Backend Lead + Product Owner approval required

## Client Generation

### Python Client

**Generation Command**: `scripts/generate-models.sh`

**Output**: `backend/app/schemas/{domain}.py`

**Tool**: `datamodel-codegen` (Pydantic v2 models)

**Validation**: Generated models must pass type checking and validation

### TypeScript Client

**Generation Command**: `openapi-generator-cli generate -i contracts/{domain}/v1/{domain}.yaml -g typescript-axios -o frontend/generated/clients/typescript/{domain}/`

**Output**: `frontend/generated/clients/typescript/{domain}/`

**Tool**: `@openapitools/openapi-generator-cli`

**Validation**: Generated clients must compile without errors

### Client Validation

**Test Protocol**:
1. Generate clients from active contracts
2. Validate client compilation (TypeScript) or import (Python)
3. Verify client matches contract specifications
4. Test client against mock servers

**CI Integration**: `.github/workflows/ci.yml` - `validate-contracts` job

## Migration Strategy

### Version Coexistence

**Policy**: Support multiple API versions simultaneously during migration period

**Implementation**:
- Version in URL path: `/api/v1/attribution/revenue/realtime`
- Version in header: `API-Version: v1`
- Separate endpoints per version

**Deprecation Timeline**:
- **Announcement**: 3 months before deprecation
- **Deprecation**: Mark endpoints as deprecated in contract
- **Removal**: Remove after 6 months deprecation period

### Consumer Migration

**Communication**:
- Release notes for breaking changes
- Migration guides with code examples
- Deprecation warnings in API responses

**Support**:
- Maintain v1 for 12 months after v2 release
- Provide migration tooling and documentation
- Offer support during migration period

## Contract Organization

### Domain-Based Structure

```
contracts/
├── attribution/
│   ├── v1/
│   │   └── attribution.yaml
│   └── baselines/
│       └── v1.0.0/
│           └── attribution.yaml
├── webhooks/
│   ├── v1/
│   │   ├── shopify.yaml
│   │   ├── stripe.yaml
│   │   ├── paypal.yaml
│   │   └── woocommerce.yaml
│   └── baselines/
│       └── v1.0.0/
│           ├── shopify.yaml
│           ├── stripe.yaml
│           ├── paypal.yaml
│           └── woocommerce.yaml
└── _common/
    └── v1/
        ├── components.yaml
        ├── pagination.yaml
        └── parameters.yaml
```

### Common Components

**Location**: `contracts/_common/v1/`

**Purpose**: Shared schemas, responses, security schemes used across all domains

**Referencing**: `$ref: '../../_common/v1/components.yaml#/components/responses/Unauthorized'`

**Versioning**: Common components versioned independently but typically aligned with domain versions

## Related Documentation

- **Contract Ownership**: `docs/architecture/contract-ownership.md`
- **Service Boundaries**: `docs/architecture/service-boundaries.md`
- **Breaking Change Detection**: `scripts/detect-breaking-changes.sh`

