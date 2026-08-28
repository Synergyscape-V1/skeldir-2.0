import type { IntegrationSourceState } from '../integration/types';
import type {
  FirstTrustEnvelopeSummary,
  FirstTrustEnvelopeTransport,
  GenerationOutcome,
  GenerationPrerequisites,
  ReadinessOutcome,
} from './types';
import { resolveStep5PrerequisiteState } from './step5StateMachine';
import {
  validateEnvelopeSummaryCore,
  validateSummaryTransportBoundary,
  type SummaryValidationFailure,
} from './summaryValidation';

function validationFailureToOutcome(
  failure: SummaryValidationFailure,
  message: string,
): GenerationOutcome {
  switch (failure) {
    case 'payload_oversized':
      return { kind: 'first_envelope_payload_oversized', message };
    case 'forbidden_fields':
      return { kind: 'first_envelope_forbidden_payload_fields', message };
    default:
      return { kind: 'first_envelope_schema_invalid', message };
  }
}

function validateOutcomeEnvelope(outcome: GenerationOutcome): GenerationOutcome {
  if (
    outcome.kind !== 'first_envelope_generated' &&
    outcome.kind !== 'first_envelope_already_exists'
  ) {
    return outcome;
  }
  const result = validateSummaryTransportBoundary(outcome.envelope);
  if (!result.ok) {
    return validationFailureToOutcome(result.failure, result.message);
  }
  return { ...outcome, envelope: result.summary };
}

function validateExistingEnvelope(
  envelope: FirstTrustEnvelopeSummary | null,
): FirstTrustEnvelopeSummary | null {
  if (!envelope) return null;
  const result = validateSummaryTransportBoundary(envelope);
  return result.ok ? result.summary : null;
}

export function hasVerifiedCommerceEvent(states: IntegrationSourceState[]): boolean {
  return states.some(
    (entry) =>
      entry.kind === 'commerce' &&
      entry.status === 'verification_ready' &&
      Boolean(entry.lastEventAt),
  );
}

function defaultEnvelope(_tenantId: string): FirstTrustEnvelopeSummary {
  const now = new Date().toISOString();
  return {
    envelopeId: 'trust_envelope_01',
    subjectRef: 'commerce_event_01',
    verifiedRevenueMinor: 125000n,
    currencyCode: 'USD',
    revenueAuthority: 'deterministic',
    attributionModel: 'last_touch',
    attributionAuthority: 'deterministic',
    confidenceStatus: 'unavailable',
    confidenceAuthority: 'unavailable',
    confidenceReason: 'Confidence is unavailable. Deterministic verification remains active.',
    benchmarkStatus: 'unavailable',
    benchmarkReason: 'No defensible benchmark exists for this segment yet.',
    policyAuthority: 'blocked',
    auditEventId: 'aud_te_001',
    generatedAt: now,
  };
}

export interface MockFirstTrustEnvelopeOptions {
  delayMs?: number;
  readinessResult?: ReadinessOutcome;
  generationResult?: GenerationOutcome;
  existingEnvelope?: FirstTrustEnvelopeSummary | null;
  denyGeneration?: boolean;
  rateLimit?: boolean;
  replayReject?: boolean;
  schemaInvalid?: boolean;
  auditUnavailable?: boolean;
  networkError?: boolean;
  generationCallCounter?: { count: number };
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

export function createMockFirstTrustEnvelopeTransport(
  options: MockFirstTrustEnvelopeOptions = {},
): FirstTrustEnvelopeTransport {
  const tenantEnvelopes = new Map<string, FirstTrustEnvelopeSummary>();
  const pendingKeys = new Map<string, string>();
  const completedKeys = new Set<string>();

  if (options.existingEnvelope) {
    tenantEnvelopes.set('tenant_placeholder', options.existingEnvelope);
  }

  return {
    async checkReadiness(_tenantId, prerequisites, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.readinessResult) return options.readinessResult;
      if (options.networkError) return { kind: 'first_envelope_network_error' };
      if (options.auditUnavailable) {
        return { kind: 'first_envelope_audit_unavailable', message: 'Audit substrate unavailable' };
      }
      if (options.denyGeneration) return { kind: 'first_envelope_permission_denied' };

      const state = resolveStep5PrerequisiteState(prerequisites);
      if (state !== 'ready_to_generate') {
        return { kind: 'first_envelope_unavailable', reason: state };
      }
      return { kind: 'first_envelope_ready' };
    },

    async generateFirstEnvelope(tenantId, idempotencyKey, signal) {
      if (options.generationCallCounter) options.generationCallCounter.count += 1;
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.generationResult) return options.generationResult;
      if (options.networkError) return { kind: 'first_envelope_network_error' };
      if (options.rateLimit) return { kind: 'first_envelope_rate_limited' };
      if (options.denyGeneration) return { kind: 'first_envelope_permission_denied' };
      if (options.auditUnavailable) {
        return { kind: 'first_envelope_audit_unavailable', message: 'Audit substrate unavailable' };
      }
      if (options.schemaInvalid) {
        return { kind: 'first_envelope_schema_invalid', message: 'Missing audit reference' };
      }

      const existing = tenantEnvelopes.get(tenantId);
      if (existing) {
        if (options.replayReject && !completedKeys.has(idempotencyKey)) {
          return {
            kind: 'first_envelope_replay_rejected',
            message: 'Replay rejected for existing envelope',
          };
        }
        return { kind: 'first_envelope_already_exists', envelope: existing };
      }

      if (pendingKeys.has(tenantId)) {
        const requestId = pendingKeys.get(tenantId)!;
        if (pendingKeys.get(tenantId) === idempotencyKey) {
          return { kind: 'first_envelope_generation_pending', requestId };
        }
      }

      pendingKeys.set(tenantId, idempotencyKey);
      await delay(50, signal);

      const envelope = defaultEnvelope(tenantId);
      tenantEnvelopes.set(tenantId, envelope);
      completedKeys.add(idempotencyKey);
      pendingKeys.delete(tenantId);

      return { kind: 'first_envelope_generated', envelope };
    },

    async getExistingFirstEnvelope(tenantId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.existingEnvelope !== undefined) return options.existingEnvelope;
      return tenantEnvelopes.get(tenantId) ?? null;
    },
  };
}

export interface FirstTrustEnvelopeClient {
  checkReadiness(
    tenantId: string,
    prerequisites: GenerationPrerequisites,
    signal?: AbortSignal,
  ): Promise<ReadinessOutcome>;
  generateFirstEnvelope(
    tenantId: string,
    idempotencyKey: string,
    signal?: AbortSignal,
  ): Promise<GenerationOutcome>;
  getExistingFirstEnvelope(
    tenantId: string,
    signal?: AbortSignal,
  ): Promise<FirstTrustEnvelopeSummary | null>;
}

export function createFirstTrustEnvelopeClient(
  transport: FirstTrustEnvelopeTransport,
): FirstTrustEnvelopeClient {
  return {
    checkReadiness: (tenantId, prerequisites, signal) =>
      transport.checkReadiness(tenantId, prerequisites, signal),
    generateFirstEnvelope: async (tenantId, idempotencyKey, signal) =>
      validateOutcomeEnvelope(
        await transport.generateFirstEnvelope(tenantId, idempotencyKey, signal),
      ),
    getExistingFirstEnvelope: async (tenantId, signal) =>
      validateExistingEnvelope(await transport.getExistingFirstEnvelope(tenantId, signal)),
  };
}

let defaultClient: FirstTrustEnvelopeClient | null = null;

export function getDefaultFirstTrustEnvelopeClient(): FirstTrustEnvelopeClient {
  if (!defaultClient) {
    defaultClient = createFirstTrustEnvelopeClient(createMockFirstTrustEnvelopeTransport());
  }
  return defaultClient;
}

export function setDefaultFirstTrustEnvelopeClient(client: FirstTrustEnvelopeClient): void {
  defaultClient = client;
}

export function resetDefaultFirstTrustEnvelopeClient(): void {
  defaultClient = null;
}

export function validateEnvelopeSummary(envelope: FirstTrustEnvelopeSummary): boolean {
  return validateEnvelopeSummaryCore(envelope);
}
