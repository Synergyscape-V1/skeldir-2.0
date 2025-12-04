# B0.2 FRONTEND IMPLEMENTATION SPECIFICATION

**Baseline Commit**: 74a3019  
**Author**: Backend Engineer Agent  
**Target**: Frontend Replit AI Agent  
**Phase**: B0.2 LLM Mock Extension

---

## SECTION 1: ENVIRONMENT CONFIGURATION

### Required Environment Variables

Update `.env` (Replit or local) with the 12 endpoints:

```env
# Core
VITE_AUTH_API_URL=http://localhost:4010
VITE_ATTRIBUTION_API_URL=http://localhost:4011
VITE_RECONCILIATION_API_URL=http://localhost:4014
VITE_EXPORT_API_URL=http://localhost:4015
VITE_HEALTH_API_URL=http://localhost:4016

# LLM Endpoint Configuration (NEW for B0.2)
VITE_LLM_INVESTIGATIONS_URL=http://localhost:4024
VITE_LLM_BUDGET_URL=http://localhost:4025
VITE_LLM_EXPLANATIONS_URL=http://localhost:4026

# Webhooks
VITE_WEBHOOK_SHOPIFY_URL=http://localhost:4020
VITE_WEBHOOK_STRIPE_URL=http://localhost:4021
VITE_WEBHOOK_WOOCOMMERCE_URL=http://localhost:4022
VITE_WEBHOOK_PAYPAL_URL=http://localhost:4023
```

---

## SECTION 2: TYPE DEFINITION GENERATION

### Command to Execute

Contracts live in `api-contracts/openapi/v1`. Generate TS types:

```bash
npx openapi-typescript api-contracts/openapi/v1/llm-investigations.yaml -o client/src/types/api/llm-investigations.ts
npx openapi-typescript api-contracts/openapi/v1/llm-budget.yaml -o client/src/types/api/llm-budget.ts
npx openapi-typescript api-contracts/openapi/v1/llm-explanations.yaml -o client/src/types/api/llm-explanations.ts
```

---

## SECTION 3: API CLIENT IMPLEMENTATION

### File 1: LLM Investigations Client

**Path**: `client/src/api/services/llm-investigations.ts`

**Implementation Template**:

```typescript
import type { InvestigationRequest, InvestigationStatusResponse } from '@/types/api/llm-investigations';
import { createHttpClient } from '../httpClient'; // existing axios/fetch wrapper

const baseUrl = import.meta.env.VITE_LLM_INVESTIGATIONS_URL;

export class LLMInvestigationsService {
  constructor(private readonly client = createHttpClient(baseUrl)) {}

  startInvestigation(payload: InvestigationRequest) {
    return this.client.post<InvestigationStatusResponse>('/api/investigations', payload);
  }

  getInvestigationStatus(investigationId: string) {
    return this.client.get<InvestigationStatusResponse>(`/api/investigations/${investigationId}/status`);
  }
}
```

### File 2: LLM Budget Optimization Client

**Path**: `client/src/api/services/llm-budget.ts`

```typescript
import type { BudgetOptimizationRequest, BudgetOptimizationResponse } from '@/types/api/llm-budget';
import { createHttpClient } from '../httpClient';

const baseUrl = import.meta.env.VITE_LLM_BUDGET_URL;

export class LLMBudgetService {
  constructor(private readonly client = createHttpClient(baseUrl)) {}

  optimizeBudget(payload: BudgetOptimizationRequest) {
    return this.client.post<BudgetOptimizationResponse>('/api/budget/optimization', payload);
  }
}
```

### File 3: LLM Explanations Client

**Path**: `client/src/api/services/llm-explanations.ts`

```typescript
import type { EntityExplanationResponse } from '@/types/api/llm-explanations';
import { createHttpClient } from '../httpClient';

const baseUrl = import.meta.env.VITE_LLM_EXPLANATIONS_URL;

export class LLMExplanationsService {
  constructor(private readonly client = createHttpClient(baseUrl)) {}

  getExplanation(entityType: string, entityId: string) {
    return this.client.get<EntityExplanationResponse>(`/api/v1/explain/${entityType}/${entityId}`);
  }
}
```

---

## SECTION 4: ASYNC POLLING HOOK IMPLEMENTATION

### Hook: `useAsyncJobPoller`

**Path**: `client/src/hooks/use-async-job-poller.ts`

**Purpose**: Poll investigation status with exponential backoff until completion.

**Requirements**:

- Accepts `jobId` and a `fetchStatus: (jobId: string) => Promise<StatusPayload>` function.
- Exponential backoff starting at 2s, capped at 10s, with jitter to avoid thundering herd.
- Returns `{ status, error, isPolling, refresh }`, where `refresh` forces an immediate poll.
- Stops polling on terminal states (`completed`, `failed`, `cancelled`).
- Clears timers on unmount to avoid memory leaks.

---

## SECTION 5: SUCCESS CRITERIA

Frontend implementation is COMPLETE when:

- [ ] `.env` contains all 12 API endpoint variables
- [ ] Type definitions generated for 3 LLM contracts
- [ ] API client services created for investigations, budget, explanations
- [ ] `useAsyncJobPoller` hook implemented
- [ ] Integration tests pass against localhost ports 4024-4026

---

## LOCAL VALIDATION NOTES

- Registry check: `python -c "import json; print(len(json.load(open('scripts/contracts/mock-registry.json'))['contracts']['llm']))"` → `3`.
- Mock spin-up (Git Bash): `bash scripts/start-prism-mocks.sh` now starts 12 mocks (ports 4010-4026) using bundled artifacts.
- LLM connectivity: `POST http://localhost:4024/api/investigations` responded with a queued investigation payload (202 expected by contract).
- Stop mocks on Windows after validation: `wmic process where "commandline like '%prism mock%'" call terminate`.
