const STORAGE_KEY = 'skeldir_first_envelope_idempotency';

export function createIdempotencyKey(tenantId: string): string {
  return `first_envelope_${tenantId}_${Date.now()}`;
}

export function getPersistedIdempotencyKey(tenantId: string): string | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { tenantId: string; key: string };
    return parsed.tenantId === tenantId ? parsed.key : null;
  } catch {
    return null;
  }
}

export function persistIdempotencyKey(tenantId: string, key: string): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ tenantId, key }));
  } catch {
    /* sessionStorage unavailable in test env — noop */
  }
}

export function clearPersistedIdempotencyKey(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* noop */
  }
}

export function resolveIdempotencyKey(tenantId: string): string {
  return getPersistedIdempotencyKey(tenantId) ?? createIdempotencyKey(tenantId);
}
