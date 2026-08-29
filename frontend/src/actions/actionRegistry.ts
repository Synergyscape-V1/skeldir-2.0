import type { GovernedActionOutcome } from './types';

const STORAGE_KEY = 'skeldir_l9_action_registry_v1';

export type RegistryStatus = 'pending' | 'completed' | 'failed';

export interface ActionRegistryEntry {
  fingerprint: string;
  idempotencyKey: string;
  status: RegistryStatus;
  outcome?: GovernedActionOutcome;
  updatedAt: string;
}

type RegistryMap = Record<string, ActionRegistryEntry>;

function readStore(): RegistryMap {
  if (typeof sessionStorage === 'undefined') return {};
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as RegistryMap;
  } catch {
    return {};
  }
}

function writeStore(map: RegistryMap): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

export function buildActionFingerprint(
  tenantId: string,
  objectType: string,
  objectId: string,
  actionKind: string,
  policyVersion = 'v1',
): string {
  return `${tenantId}:${objectType}:${objectId}:${actionKind}:${policyVersion}`;
}

export function registerActionPending(fingerprint: string, idempotencyKey: string): void {
  const map = readStore();
  map[fingerprint] = {
    fingerprint,
    idempotencyKey,
    status: 'pending',
    updatedAt: new Date().toISOString(),
  };
  writeStore(map);
}

export function registerActionOutcome(fingerprint: string, outcome: GovernedActionOutcome): void {
  const map = readStore();
  map[fingerprint] = {
    fingerprint,
    idempotencyKey: outcome.idempotencyKey,
    status: outcome.status === 'success' ? 'completed' : 'failed',
    outcome,
    updatedAt: new Date().toISOString(),
  };
  writeStore(map);
}

export function getActionRegistryEntry(fingerprint: string): ActionRegistryEntry | null {
  return readStore()[fingerprint] ?? null;
}

export function clearActionRegistryForTests(): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(STORAGE_KEY);
}

export function clearActionRegistryEntry(fingerprint: string): void {
  const map = readStore();
  delete map[fingerprint];
  writeStore(map);
}

export function listActionRegistryEntries(): ActionRegistryEntry[] {
  return Object.values(readStore());
}
