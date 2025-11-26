# Type Safety Maintenance Guide

## Overview

This document describes how to maintain TypeScript types derived from OpenAPI contracts for the Skeldir 2.0 frontend application.

## Type Generation Strategy

Due to YAML syntax issues in `base.yaml` (line 155), we use a hybrid approach:

| Contract | Strategy | File | Last Updated |
|----------|----------|------|--------------|
| attribution.yaml | ✅ Auto-generated | `client/src/types/api/attribution.ts` | Auto |
| auth.yaml | ⚠️  Manual | `client/src/types/api/auth.ts` | Manual |
| reconciliation.yaml | ⚠️ Manual | `client/src/types/api/reconciliation.ts` | Manual |
| export.yaml | ⚠️ Manual | `client/src/types/api/export.ts` | Manual |
| health.yaml | ⚠️ Manual | `client/src/types/api/health.ts` | Manual |

## Auto-Generation (attribution.yaml)

### Regenerate Attribution Types

```bash
npx openapi-typescript docs/api/contracts/attribution.yaml -o client/src/types/api/attribution.ts
```

**When to regenerate:**
- After `attribution.yaml` contract changes
- When new attribution endpoints are added
- When response schemas are modified

## Manual Type Updates

For contracts that reference `base.yaml` (auth, reconciliation, export, health), types must be manually updated when contracts change.

### Update Workflow

1. **Detect Contract Changes**
   ```bash
   # Check for contract modifications
   git diff HEAD docs/api/contracts/
   ```

2. **Review Contract Diff**
   - Identify changed endpoints
   - Note new/modified schemas
   - Check for breaking changes

3. **Update TypeScript Types**
   - Edit corresponding `client/src/types/api/*.ts` file
   - Match TypeScript interfaces to YAML schemas
   - Ensure snake_case property names (API convention)
   - Add JSDoc comments for clarity

4. **Validate Types**
   ```bash
   npm run check
   ```

### Manual Type Template

When adding a new endpoint, follow this pattern:

```typescript
// Request/Response Interfaces
export interface NewEndpointRequest {
  property_name: string; // snake_case matches API
  optional_field?: number;
}

export interface NewEndpointResponse {
  result_data: string;
  timestamp: string;
}

// Add to paths interface
export interface paths {
  "/api/service/new-endpoint": {
    post: {
      parameters: {
        header: {
          "X-Correlation-ID": string;
          Authorization?: string;
        };
      };
      requestBody: {
        content: {
          "application/json": NewEndpointRequest;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": NewEndpointResponse;
          };
        };
        401: {
          content: {
            "application/problem+json": ProblemDetails;
          };
        };
      };
    };
  };
}
```

## Breaking Change Detection

### Contract Version Tracking

Monitor `CONTRACT_VERSIONS.md` for:
- Contract tag/version changes
- Checksum mismatches
- Breaking change notifications

### Type Validation Checklist

Before deploying type changes:

- [ ] All existing API calls compile without errors
- [ ] No missing required properties
- [ ] Optional properties correctly marked with `?`
- [ ] Response types match mock server data
- [ ] Error types include `ProblemDetails` (RFC7807)

## Common Issues

### Issue: base.yaml Syntax Error

**Problem:** `openapi-typescript` fails on auth/reconciliation/export/health contracts  
**Cause:** Malformed YAML at `base.yaml:155:81`  
**Solution:** Use manual types until base.yaml is fixed upstream

### Issue: Type Mismatch with API

**Problem:** TypeScript error when calling API  
**Diagnosis:**
```bash
# Compare contract schema vs TypeScript interface
npx openapi-typescript docs/api/contracts/service.yaml --stdout | grep -A 10 "paths"
```
**Solution:** Update TypeScript interface to match contract

### Issue: Missing Correlation ID

**Problem:** API returns 400 "Missing X-Correlation-ID"  
**Solution:** Ensure all `paths` interfaces include:
```typescript
parameters: {
  header: {
    "X-Correlation-ID": string;
  };
}
```

## Automation Roadmap

### Phase 1: Fix base.yaml (Backend Team)
- Resolve YAML syntax error at line 155
- Validate all $ref resolution works
- Test with `openapi-typescript --validate`

### Phase 2: Full Auto-Generation
Once base.yaml is fixed:
```bash
#!/bin/bash
# scripts/generate-types.sh

npx openapi-typescript docs/api/contracts/auth.yaml -o client/src/types/api/auth.ts
npx openapi-typescript docs/api/contracts/attribution.yaml -o client/src/types/api/attribution.ts
npx openapi-typescript docs/api/contracts/reconciliation.yaml -o client/src/types/api/reconciliation.ts
npx openapi-typescript docs/api/contracts/export.yaml -o client/src/types/api/export.ts
npx openapi-typescript docs/api/contracts/health.yaml -o client/src/types/api/health.ts

echo "✅ All types regenerated"
```

### Phase 3: CI/CD Integration
- Add type generation to pre-commit hook
- Automated contract drift detection
- Breaking change notifications

## Support

For type-related issues:
1. Check TypeScript compiler errors: `npm run check`
2. Validate contract syntax: `npx @stoplight/spectral-cli lint docs/api/contracts/*.yaml`
3. Review this guide's troubleshooting section
4. Consult `CONTRACT_VERSIONS.md` for contract history

---

*Last Updated: 2025-11-11*  
*Next Review: When base.yaml is fixed*
