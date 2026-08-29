export const TRUST_ENVELOPE_DETAIL_COPY = {
  title: 'TrustEnvelope',
  pageQuestion:
    'What is verified, what policy allows, and what evidence proves this trust object?',
  panels: {
    subject: {
      title: 'A. Subject',
      subjectType: 'Subject type',
      subjectIdentifier: 'Subject identifier',
      relatedClaimId: 'Related claim ID',
      relatedChannel: 'Related channel',
      sourceSystem: 'Source system',
      timeWindow: 'Time window',
      openRelatedClaim: (claimId: string) => `Open claim ${claimId}`,
      openRelatedChannel: (label: string) => `Open channel ${label}`,
    },
    deterministicTruth: {
      title: 'B. Deterministic Truth',
      currency: 'Currency',
      commerceEvidenceSource: 'Commerce evidence source',
      comparisonLabel: 'Claim Comparison',
      claimedRevenue: 'Claimed revenue',
      verifiedRevenue: 'Verified revenue',
      difference: 'Difference',
    },
    attribution: {
      title: 'C. Attribution Model',
      selectedModel: 'Selected attribution model',
      modelFamily: 'Model family',
      modelAgreementTier: 'Revenue reliability tier',
      allocationResult: 'Allocation result',
      allocationLabel: (channel: string, percent: number) =>
        `${channel} assigned ${percent}% of verified revenue`,
    },
    confidence: {
      title: 'D. Confidence Metadata',
      credibleInterval95: '95% credible interval',
      posteriorSupport: 'Posterior support',
      modelFreshness: 'Model freshness',
      delayedStatus: 'Confidence delayed',
    },
    benchmark: {
      title: 'E. Benchmark Metadata',
      rawBenchmark: 'Raw benchmark',
      decisionSafeBenchmark: 'Decision-safe benchmark',
      sourceClass: 'Source class',
      coverageClass: 'Coverage class',
      suppressionReason: 'Suppression reason',
      comparableToPrevious: 'Comparable to previous',
      actionability: 'Actionability',
      comparableYes: 'Yes',
      comparableNo: 'No',
      nullLiteral: 'null',
    },
    policyAuthority: {
      title: 'F. Policy Authority',
      authorityExplanation: 'Authority explanation',
      allowedActions: 'Allowed actions',
      blockedActions: 'Blocked actions',
      auditRequirement: 'Audit requirement',
    },
    audit: {
      title: 'Audit record',
      auditReference: 'Audit ref',
      guidance:
        'Forensic verification lives in the Audit Ledger. This reference links compliance engineers to the full record without exposing hashes in the marketer UI.',
    },
  },
  status: {
    issued: 'Issued',
    superseded: 'Superseded',
    invalid: 'Invalid',
  },
  cockpit: {
    ariaLabel: 'Decision verdict summary',
    verifiedRevenue: 'Verified revenue',
    policyAuthority: 'Policy authority',
  },
  rooms: {
    storyboardAriaLabel: 'Storyboard — human-readable trust testimony',
  },
} as const;
