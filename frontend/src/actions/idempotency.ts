import type { TrustEnvelopeJsonContract } from '../detail/types';
import {
  applyRequiredJsonNulls,
  buildCanonicalOrderedContract,
} from '../trustIndex/trustEnvelopeJsonContract';
import {
  buildActionFingerprint,
  clearActionRegistryEntry,
  clearActionRegistryForTests,
  getActionRegistryEntry,
  registerActionOutcome,
  registerActionPending,
} from './actionRegistry';
import { clearClipboardStageForTests } from './bounds';
import type { GovernedActionOutcome } from './types';

const pendingKeys = new Set<string>();
const completedOutcomes = new Map<string, { actionId: string; auditEventId: string }>();

let idCounter = 0;

export { buildActionFingerprint } from './actionRegistry';

export function fingerprintFromIdempotencyKey(key: string): string {
  return key.startsWith('idem_') ? key.slice(5) : key;
}

export function generateIdempotencyKey(
  tenantId: string,
  objectType: string,
  objectId: string,
  actionKind: string,
  policyVersion = 'v1',
): string {
  const fingerprint = buildActionFingerprint(tenantId, objectType, objectId, actionKind, policyVersion);
  return `idem_${fingerprint}`;
}

export function resetIdempotencyStoreForTests(): void {
  pendingKeys.clear();
  completedOutcomes.clear();
  clearActionRegistryForTests();
  clearClipboardStageForTests();
  idCounter = 0;
}

/** Simulates hard refresh: module memory cleared while sessionStorage registry survives */
export function simulateHardRefreshForTests(): void {
  pendingKeys.clear();
  completedOutcomes.clear();
  idCounter = 0;
}

export function markIdempotencyPending(key: string): boolean {
  const fingerprint = fingerprintFromIdempotencyKey(key);
  const registry = getActionRegistryEntry(fingerprint);
  if (registry?.status === 'completed' || registry?.status === 'pending') return false;
  if (pendingKeys.has(key) || completedOutcomes.has(key)) return false;
  pendingKeys.add(key);
  registerActionPending(fingerprint, key);
  return true;
}

export function clearIdempotencyPending(key: string): void {
  pendingKeys.delete(key);
  clearActionRegistryEntry(fingerprintFromIdempotencyKey(key));
}

export function recordIdempotencySuccess(
  key: string,
  actionId: string,
  auditEventId: string,
  outcome?: GovernedActionOutcome,
): void {
  pendingKeys.delete(key);
  completedOutcomes.set(key, { actionId, auditEventId });
  if (outcome) {
    registerActionOutcome(fingerprintFromIdempotencyKey(key), outcome);
  }
}

export function getIdempotencyReplay(key: string): { actionId: string; auditEventId: string } | null {
  const fingerprint = fingerprintFromIdempotencyKey(key);
  const registry = getActionRegistryEntry(fingerprint);
  if (registry?.status === 'completed' && registry.outcome?.actionId && registry.outcome.auditEventId) {
    return { actionId: registry.outcome.actionId, auditEventId: registry.outcome.auditEventId };
  }
  return completedOutcomes.get(key) ?? null;
}

export function recoverRegistryOutcome(fingerprint: string): GovernedActionOutcome | null {
  const entry = getActionRegistryEntry(fingerprint);
  return entry?.outcome ?? null;
}

export function isRegistryPending(fingerprint: string): boolean {
  return getActionRegistryEntry(fingerprint)?.status === 'pending';
}

/** Canonical export-safe JSON — not DOM-derived */
export function buildCanonicalTrustEnvelopeJson(contract: TrustEnvelopeJsonContract): string {
  const ordered = buildCanonicalOrderedContract(contract);
  return JSON.stringify(applyRequiredJsonNulls(ordered), null, 2);
}

export function createActionId(prefix: string): string {
  idCounter += 1;
  return `${prefix}_${String(idCounter).padStart(4, '0')}`;
}

export function createAuditEventId(prefix: string): string {
  idCounter += 1;
  return `aud_action_${prefix}_${String(idCounter).padStart(4, '0')}`;
}
