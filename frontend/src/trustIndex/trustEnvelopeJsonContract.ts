import type { TrustEnvelopeDetailDTO, TrustEnvelopeJsonContract } from '../detail/types';

export const TRUST_ENVELOPE_REQUIRED_NULLABLE_PATHS = [
  ['confidenceMetadata', 'fallbackReason'],
  ['benchmarkMetadata', 'suppressionReason'],
  ['auditAndSignature', 'artifactRef'],
  ['auditAndSignature', 'artifactHash'],
  ['auditAndSignature', 'signature'],
  ['auditAndSignature', 'signatureAlgorithm'],
  ['auditAndSignature', 'keyId'],
] as const;

export const TRUST_ENVELOPE_REQUIRED_NULLABLE_KEYS = TRUST_ENVELOPE_REQUIRED_NULLABLE_PATHS.map((path) =>
  path.join('.'),
);

function getNestedValue(root: Record<string, unknown>, path: readonly string[]): unknown {
  let cursor: unknown = root;
  for (const segment of path) {
    if (cursor === null || typeof cursor !== 'object') return undefined;
    cursor = (cursor as Record<string, unknown>)[segment];
  }
  return cursor;
}

function setNestedValue(root: Record<string, unknown>, path: readonly string[], value: null): void {
  let cursor = root;
  for (let index = 0; index < path.length - 1; index += 1) {
    const segment = path[index];
    const next = cursor[segment];
    if (typeof next !== 'object' || next === null) {
      cursor[segment] = {};
    }
    cursor = cursor[segment] as Record<string, unknown>;
  }
  cursor[path[path.length - 1]] = value;
}

export function applyRequiredJsonNulls(
  value: TrustEnvelopeJsonContract | Record<string, unknown>,
): Record<string, unknown> {
  const normalized = JSON.parse(JSON.stringify(value)) as Record<string, unknown>;
  for (const path of TRUST_ENVELOPE_REQUIRED_NULLABLE_PATHS) {
    if (getNestedValue(normalized, path) === undefined) {
      setNestedValue(normalized, path, null);
    }
  }
  return normalized;
}

export function stringifyTrustEnvelopeJsonContract(
  value: TrustEnvelopeJsonContract | Record<string, unknown>,
): string {
  return JSON.stringify(applyRequiredJsonNulls(value), null, 2);
}

function parseChannelId(href: string): string {
  const segments = href.split('/').filter(Boolean);
  return segments[segments.length - 1] ?? href;
}

function parseSourceSystems(sourceSystem: string): string[] {
  return sourceSystem.split('·').map((part) => part.trim()).filter(Boolean);
}

function parseTimeWindow(timeWindowLabel: string): { start: string; end: string; timezone: string } {
  const match = timeWindowLabel.match(/^(\d{4}-\d{2}-\d{2})\s*→\s*(\d{4}-\d{2}-\d{2})\s*\(([^)]+)\)$/);
  if (!match) {
    return { start: 'unknown', end: 'unknown', timezone: 'UTC' };
  }
  return { start: match[1], end: match[2], timezone: match[3] };
}

function buildProvenanceChainJson(_detail: TrustEnvelopeDetailDTO) {
  return [];
}

export function buildTrustEnvelopeJsonContract(detail: TrustEnvelopeDetailDTO): TrustEnvelopeJsonContract {
  const verifiedMinor = Number(detail.deterministicTruth.verifiedRevenueMinor);
  const claimedMinor = Number(detail.deterministicTruth.claimedRevenueMinor);
  const differenceMinor = Number(detail.deterministicTruth.differenceMinor);
  const rateBps = detail.deterministicTruth.differenceRateBps;
  const currencyCode = detail.deterministicTruth.currencyCode;
  const authority = 'commerce_verified';
  const canonicalEnvelopeId = detail.canonicalEnvelopeId ?? null;
  const displayEnvelopeId = canonicalEnvelopeId ?? detail.envelopeId;

  return {
    envelopeId: displayEnvelopeId,
    canonicalEnvelopeId,
    status: detail.status,
    createdAt: detail.createdAt,
    tenantId: detail.tenantId,
    schemaVersion: '1.0',
    subject: {
      subjectType: detail.subject.subjectType,
      identifier: detail.subject.subjectIdentifier,
      relatedClaimId: detail.subject.relatedClaimId,
      relatedChannel: {
        label: detail.subject.relatedChannelLabel,
        channelId: parseChannelId(detail.subject.relatedChannelHref),
      },
      sourceSystems: parseSourceSystems(detail.subject.sourceSystem),
      timeWindow: parseTimeWindow(detail.subject.timeWindowLabel),
    },
    deterministicTruth: {
      verifiedRevenue: {
        amountMinor: verifiedMinor,
        currencyCode,
        authority,
      },
      claimComparison: {
        claimedRevenue: { amountMinor: claimedMinor, currencyCode, authority },
        verifiedRevenue: { amountMinor: verifiedMinor, currencyCode, authority },
        difference: { amountMinor: differenceMinor, currencyCode, authority, rateBps },
      },
      commerceEvidenceSource: detail.deterministicTruth.commerceEvidenceSource,
    },
    attributionModel: {
      selectedModel: detail.attribution.selectedModel,
      modelFamily: detail.attribution.modelFamily,
      agreementTier: detail.attribution.modelAgreementTier,
      allocationResult: {
        channel: detail.attribution.allocationChannel,
        allocationPercent: detail.attribution.allocationPercent,
        authority:
          detail.attribution.allocationAuthority === 'deterministic'
            ? 'Deterministic'
            : detail.attribution.allocationAuthority,
      },
      boundaryNote: detail.attribution.boundaryNote,
    },
    confidenceMetadata: {
      status: detail.confidence.status,
      credibleInterval95:
        detail.confidence.status === 'available' &&
        detail.confidence.intervalLower !== undefined &&
        detail.confidence.intervalUpper !== undefined
          ? [detail.confidence.intervalLower, detail.confidence.intervalUpper]
          : null,
      posteriorSupport:
        detail.confidence.status === 'available' && detail.confidence.posteriorSupport !== undefined
          ? detail.confidence.posteriorSupport
          : null,
      modelFreshness:
        detail.confidence.status === 'available' ? detail.confidence.modelFreshnessAt ?? null : null,
      authority:
        detail.confidence.authority === 'probabilistic' ? 'Probabilistic' : detail.confidence.authority,
      note: detail.confidence.boundaryNote,
      fallbackReason: null,
    },
    benchmarkMetadata: {
      rawBenchmark: {
        value: detail.benchmark.rawBenchmark,
        authority:
          detail.benchmark.benchmarkAuthority === 'benchmark'
            ? 'Benchmark'
            : detail.benchmark.benchmarkAuthority,
      },
      decisionSafeBenchmark: {
        value: detail.benchmark.decisionSafeBenchmark,
        authority:
          detail.benchmark.benchmarkAuthority === 'benchmark'
            ? 'Benchmark'
            : detail.benchmark.benchmarkAuthority,
      },
      sourceClass: detail.benchmark.sourceClass,
      coverageClass: detail.benchmark.coverageClass,
      suppressionReason: detail.benchmark.suppressionReason,
      comparableToPrevious: detail.benchmark.comparableToPrevious,
      actionability: detail.benchmark.actionability,
    },
    policyAuthority: {
      state: detail.policyAuthority.state,
      explanation: detail.policyAuthority.explanation,
      allowedActions: detail.policyAuthority.allowedActions,
      blockedActions: detail.policyAuthority.blockedActions,
      auditRequirement: detail.policyAuthority.auditRequirement,
    },
    provenanceChain: buildProvenanceChainJson(detail),
    auditAndSignature: {
      auditReference: detail.auditReference,
      accessEvents: 0,
      artifactRef: null,
      artifactHash: '',
      signature: null,
      signatureAlgorithm: null,
      keyId: null,
      canonicalizationVersion: 'operator-view-v1',
      semanticTruthHash: '',
      signatureHash: null,
    },
  };
}

export function buildCanonicalOrderedContract(contract: TrustEnvelopeJsonContract): Record<string, unknown> {
  return {
    envelopeId: contract.envelopeId,
    canonicalEnvelopeId: contract.canonicalEnvelopeId,
    status: contract.status,
    createdAt: contract.createdAt,
    tenantId: contract.tenantId,
    schemaVersion: contract.schemaVersion,
    subject: contract.subject,
    deterministicTruth: contract.deterministicTruth,
    attributionModel: contract.attributionModel,
    confidenceMetadata: contract.confidenceMetadata,
    benchmarkMetadata: contract.benchmarkMetadata,
    policyAuthority: contract.policyAuthority,
    provenanceChain: contract.provenanceChain
      ? [...contract.provenanceChain].sort((left, right) => {
          const timeCompare = left.timestamp.localeCompare(right.timestamp);
          if (timeCompare !== 0) return timeCompare;
          return left.evidenceReference.localeCompare(right.evidenceReference);
        })
      : null,
    auditAndSignature: contract.auditAndSignature,
  };
}

export function buildMinimalTrustEnvelopeJsonContract(
  overrides: Partial<TrustEnvelopeJsonContract> = {},
): TrustEnvelopeJsonContract {
  const base = buildTrustEnvelopeJsonContract({
    envelopeId: 'env_0001',
    canonicalEnvelopeId: 'tenv_test',
    tenantId: 'tenant_test_001',
    status: 'issued',
    createdAt: '2026-07-02T13:24:00Z',
    subject: {
      subjectType: 'Revenue Claim Envelope',
      subjectIdentifier: 'subject_test',
      relatedClaimId: 'claim_0001',
      relatedClaimHref: '/app/claims/claim_0001',
      relatedChannelLabel: 'Meta Ads · Retargeting',
      relatedChannelHref: '/app/channels/ch_1',
      sourceSystem: 'Shopify · Stripe · Meta',
      timeWindowLabel: '2026-06-01 → 2026-06-30 (UTC)',
    },
    deterministicTruth: {
      verifiedRevenueMinor: 1n,
      claimedRevenueMinor: 1n,
      differenceMinor: 0n,
      differenceRateBps: 0,
      currencyCode: 'USD',
      matchVerdictStatus: 'verified',
      commerceEvidenceSource: 'fixture',
    },
    attribution: {
      selectedModel: 'Position-Based 40/20/40',
      modelFamily: 'Deterministic heuristic',
      modelAgreementTier: 'Moderate agreement',
      allocationChannel: 'Meta Ads',
      allocationPercent: 41.8,
      allocationAuthority: 'deterministic',
      boundaryNote:
        'Attribution models are deterministic heuristics and do not prove causal lift.',
    },
    confidence: {
      status: 'unavailable',
      authority: 'unavailable',
      boundaryNote: 'Confidence is advisory and cannot create financial truth.',
      reason: 'Confidence is unavailable. Deterministic verification remains active.',
    },
    benchmark: {
      status: 'unavailable',
      rawBenchmark: 'n/a',
      decisionSafeBenchmark: 'n/a',
      benchmarkAuthority: 'benchmark',
      sourceClass: 'n/a',
      coverageClass: 'n/a',
      suppressionReason: null,
      comparableToPrevious: false,
      actionability: 'blocked',
      reason: 'Benchmark is unavailable. Deterministic verification remains active.',
    },
    policyAuthority: {
      state: 'blocked',
      explanation: 'Policy authority is blocked for this fixture.',
      allowedActions: [],
      blockedActions: ['All consequence-bearing actions'],
      auditRequirement: 'All consequence-bearing actions are written to the Audit Ledger.',
    },
    auditReference: 'AUD-FIXTURE',
    versionStamp: 'v1',
  });
  return { ...base, ...overrides };
}
