import type {
  BudgetSimulationDetailDTO,
  ChannelDetailDTO,
  ClaimDetailDTO,
  ExceptionDetailDTO,
  TrustEnvelopeDetailDTO,
  TrustEnvelopeJsonContract,
} from './types';
import { MAX_RELATED_ITEMS } from './types';
import { POLICY_AUTHORITY_STATES } from '../lib/types';
import {
  TRUST_ENVELOPE_REQUIRED_NULLABLE_KEYS,
  TRUST_ENVELOPE_REQUIRED_NULLABLE_PATHS,
} from '../trustIndex/trustEnvelopeJsonContract';

export { TRUST_ENVELOPE_REQUIRED_NULLABLE_KEYS, TRUST_ENVELOPE_REQUIRED_NULLABLE_PATHS };

const FORBIDDEN_DETAIL_PATTERNS = [
  /@/,
  /\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/,
  /Bearer\s+/i,
  /sk_live_/i,
  /whsec_/i,
  /raw_headers/i,
  /user_agent/i,
];

function getNestedValue(root: Record<string, unknown>, path: readonly string[]): unknown {
  let cursor: unknown = root;
  for (const segment of path) {
    if (cursor === null || typeof cursor !== 'object') return undefined;
    cursor = (cursor as Record<string, unknown>)[segment];
  }
  return cursor;
}

function hasNestedKey(root: Record<string, unknown>, path: readonly string[]): boolean {
  let cursor: unknown = root;
  for (let index = 0; index < path.length - 1; index += 1) {
    const segment = path[index];
    if (cursor === null || typeof cursor !== 'object' || !(segment in (cursor as Record<string, unknown>))) {
      return false;
    }
    cursor = (cursor as Record<string, unknown>)[segment];
  }
  const leaf = path[path.length - 1];
  return cursor !== null && typeof cursor === 'object' && leaf in (cursor as Record<string, unknown>);
}

function containsForbiddenPayload(value: unknown): boolean {
  const text = JSON.stringify(value, (_key, v) => (typeof v === 'bigint' ? v.toString() : v));
  return FORBIDDEN_DETAIL_PATTERNS.some((p) => p.test(text));
}

export function validateRouteIdentity(routeId: string, dtoId: string): boolean {
  return routeId === dtoId;
}

export function validateClaimDetailDto(dto: ClaimDetailDTO, routeClaimId: string, tenantId: string) {
  if (!validateRouteIdentity(routeClaimId, dto.claimId)) {
    return { ok: false as const, kind: 'object_id_mismatch' as const };
  }
  if (dto.tenantId !== tenantId) {
    return { ok: false as const, kind: 'scope_denied' as const };
  }
  if (containsForbiddenPayload(dto)) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  if (!dto.defaultAttributionModel?.trim()) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  if (dto.verificationStatus === 'unverified') {
    if (!dto.unverifiedReason?.trim()) {
      return { ok: false as const, kind: 'schema_invalid' as const };
    }
    return { ok: true as const };
  }
  if (!dto.paidAttribution?.length || !dto.claimEvents?.length) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  if (!Array.isArray(dto.journeyOrigins)) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  return { ok: true as const };
}

/** Agent/forensic contract validation — not used by human operator views. */
export function validateTrustEnvelopeJsonContract(json: TrustEnvelopeJsonContract): {
  ok: boolean;
  missingNullables?: string[];
} {
  const normalized = json as unknown as Record<string, unknown>;
  const missingNullables = TRUST_ENVELOPE_REQUIRED_NULLABLE_PATHS.filter((path) => {
    if (!hasNestedKey(normalized, path)) return true;
    const value = getNestedValue(normalized, path);
    return value === undefined;
  }).map((path) => path.join('.'));
  if (missingNullables.length > 0) {
    return { ok: false, missingNullables };
  }
  if (containsForbiddenPayload(json)) {
    return { ok: false };
  }
  return { ok: true };
}

export function validateTrustEnvelopeDetailDto(
  dto: TrustEnvelopeDetailDTO,
  routeEnvelopeId: string,
  tenantId: string,
) {
  if (!validateRouteIdentity(routeEnvelopeId, dto.envelopeId)) {
    return { ok: false as const, kind: 'object_id_mismatch' as const };
  }
  if (dto.tenantId !== tenantId) {
    return { ok: false as const, kind: 'scope_denied' as const };
  }
  if (!dto.auditReference?.trim()) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  const subject = dto.subject;
  if (
    !subject.subjectType ||
    !subject.subjectIdentifier ||
    !subject.relatedClaimId ||
    !subject.relatedClaimHref ||
    !subject.relatedChannelLabel ||
    !subject.relatedChannelHref ||
    !subject.sourceSystem ||
    !subject.timeWindowLabel
  ) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  const truth = dto.deterministicTruth;
  if (
    !truth.currencyCode ||
    !truth.commerceEvidenceSource ||
    truth.verifiedRevenueMinor === undefined ||
    truth.claimedRevenueMinor === undefined ||
    truth.differenceMinor === undefined
  ) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  const attribution = dto.attribution;
  if (
    !attribution.selectedModel ||
    !attribution.modelFamily ||
    !attribution.modelAgreementTier ||
    !attribution.allocationChannel ||
    attribution.allocationPercent === undefined ||
    !attribution.allocationAuthority ||
    !attribution.boundaryNote
  ) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  if (!attribution.boundaryNote.toLowerCase().includes('do not prove causal lift')) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  const confidence = dto.confidence;
  if (!confidence.boundaryNote) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  if (!confidence.boundaryNote.toLowerCase().includes('cannot create financial truth')) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  if (confidence.status === 'available') {
    if (
      confidence.intervalLower === undefined ||
      confidence.intervalUpper === undefined ||
      confidence.posteriorSupport === undefined ||
      !confidence.modelFreshnessAt
    ) {
      return { ok: false as const, kind: 'schema_invalid' as const };
    }
  }
  const benchmark = dto.benchmark;
  if (benchmark.status === 'available') {
    if (
      !benchmark.rawBenchmark ||
      !benchmark.decisionSafeBenchmark ||
      !benchmark.sourceClass ||
      !benchmark.coverageClass ||
      !benchmark.actionability ||
      benchmark.comparableToPrevious === undefined
    ) {
      return { ok: false as const, kind: 'schema_invalid' as const };
    }
    if (benchmark.suppressionReason !== null && !benchmark.suppressionReason.trim()) {
      return { ok: false as const, kind: 'schema_invalid' as const };
    }
  }
  const policyAuthority = dto.policyAuthority;
  if (
    !POLICY_AUTHORITY_STATES.includes(policyAuthority.state) ||
    !policyAuthority.explanation ||
    policyAuthority.allowedActions.length === 0 ||
    policyAuthority.blockedActions.length === 0 ||
    !policyAuthority.auditRequirement
  ) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  return { ok: true as const };
}

export function validateChannelDetailDto(
  dto: ChannelDetailDTO,
  routeChannelId: string,
  tenantId: string,
) {
  if (!validateRouteIdentity(routeChannelId, dto.channelId)) {
    return { ok: false as const, kind: 'object_id_mismatch' as const };
  }
  if (dto.tenantId !== tenantId) {
    return { ok: false as const, kind: 'scope_denied' as const };
  }
  if (
    dto.relatedClaims.length > MAX_RELATED_ITEMS ||
    dto.relatedEnvelopes.length > MAX_RELATED_ITEMS
  ) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  if (!dto.modelComparisonCopy.includes('do not prove causal lift')) {
    return { ok: false as const, kind: 'schema_invalid' as const };
  }
  return { ok: true as const };
}

export function validateExceptionDetailDto(
  dto: ExceptionDetailDTO,
  routeExceptionId: string,
  tenantId: string,
) {
  if (!validateRouteIdentity(routeExceptionId, dto.exceptionId)) {
    return { ok: false as const, kind: 'object_id_mismatch' as const };
  }
  if (dto.tenantId !== tenantId) {
    return { ok: false as const, kind: 'scope_denied' as const };
  }
  return { ok: true as const };
}

export function validateBudgetSimulationDetailDto(
  dto: BudgetSimulationDetailDTO,
  routeSimulationId: string,
  tenantId: string,
) {
  if (!validateRouteIdentity(routeSimulationId, dto.simulationId)) {
    return { ok: false as const, kind: 'object_id_mismatch' as const };
  }
  if (dto.tenantId !== tenantId) {
    return { ok: false as const, kind: 'scope_denied' as const };
  }
  return { ok: true as const };
}
