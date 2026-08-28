export type ExcludeFromBudgetOutcome =
  | { kind: 'success'; claimId: string }
  | { kind: 'error'; message: string };

export type ExcludeFromBudgetTestMode = 'default' | 'error';

let testMode: ExcludeFromBudgetTestMode = 'default';

export function setExcludeFromBudgetTestMode(mode: ExcludeFromBudgetTestMode): void {
  testMode = mode;
}

export function resetExcludeFromBudgetTestMode(): void {
  testMode = 'default';
}

export interface ExcludeFromBudgetClient {
  excludeClaim(tenantId: string, claimId: string, signal?: AbortSignal): Promise<ExcludeFromBudgetOutcome>;
}

export function createExcludeFromBudgetClient(): ExcludeFromBudgetClient {
  return {
    async excludeClaim(tenantId, claimId, signal) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      if (!tenantId.trim() || !claimId.trim()) {
        return { kind: 'error', message: 'Unable to exclude this claim from the budget simulator.' };
      }
      if (testMode === 'error') {
        return { kind: 'error', message: 'Unable to exclude this claim from the budget simulator.' };
      }
      return { kind: 'success', claimId };
    },
  };
}

let defaultClient: ExcludeFromBudgetClient | null = null;

export function getDefaultExcludeFromBudgetClient(): ExcludeFromBudgetClient {
  if (!defaultClient) defaultClient = createExcludeFromBudgetClient();
  return defaultClient;
}

export function resetDefaultExcludeFromBudgetClient(): void {
  defaultClient = null;
}
