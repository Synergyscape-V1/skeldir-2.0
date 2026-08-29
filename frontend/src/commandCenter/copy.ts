export const COMMAND_CENTER_COPY = {
  pageTitle: 'Overview',
  pageQuestion:
    'What needs your attention, what is verified, and what can safely be acted on?',
  lastUpdated: (relative: string) => relative,
  urgencyCopy: (count: number) =>
    `${count} issue${count === 1 ? '' : 's'} blocking your budget`,
  urgencyAllClear: 'All clear. Your budget is ready for action.',
  staleAggregate: 'Aggregate data may be stale. Refresh or review source ledgers before acting.',
  partialAggregate: 'Some aggregate sections are unavailable. Deterministic sections remain authoritative.',
  noPriorityIssues: 'No trust issues need review.',
  viewAllClaims: 'View all claims',
  trustApiReadFailed: 'Trust API read failed. No financial truth was changed.',
  killSwitchReadOnly:
    'Trust API paused. External trust reads are paused by an audited control-plane switch. Internal read-only review remains available.',
  /** @deprecated CDO Audit 1 — singular top-issue routing is a contract violation. */
  reviewTopIssue: 'Review top issue',
  reviewIssues: (count: number) => `Review issues (${count})`,
  viewIssuesReadOnly: (count: number) => `View issues (${count})`,
  reviewIssuesArrow: 'Review issues →',
  goToBudgetSimulation: 'Go to Budget Simulation →',
  priorityDrawerTitle: (count: number) => `Issues blocking action (${count})`,
  priorityIssueApproved: 'Approved ✓',
  priorityDismissAll: 'Dismiss all',
  priorityDismissAllAdminOnly: 'Dismiss all requires admin',
  viewLatestEnvelope: 'View latest TrustEnvelope',
  triage: {
    backToQueue: 'Back to Queue',
    exitTriage: 'Exit Triage',
    resolvingIssue: (index: number, total: number, title: string) =>
      `Resolving Issue ${index} of ${total}: ${title}`,
    approveAndAdvance: 'Approve & Advance',
    authorizingPolicy: 'Authorizing policy...',
    successHeadline: 'Simulation Authorized.',
    successSubcopy: 'Budget execution approved. Routing to next issue...',
    allClearHeadline: 'All Blockers Cleared.',
    allClearSubcopy: 'Your budget is safe to execute. No further review is required.',
    returnToDashboard: 'Return to Dashboard',
    markReviewedAndAdvance: 'Mark reviewed & Advance',
    advanceToast: (title: string, remaining: number) =>
      `${title} resolved. ${remaining} issue${remaining === 1 ? '' : 's'} remain.`,
  },
  verifiedRevenueTrend: 'Verified revenue trend',
  verifiedRevenueTrendSubtitle: 'Commerce-backed verified revenue',
  trendWindowLabel: 'Last 30 days',
  channelTrustTable: 'Channel trust snapshot',
  channelTrustGroupBy: {
    groupLabel: 'Group channel trust snapshot by',
    platform: 'Group by platform',
    campaignClass: 'Group by campaign class',
    commerceRail: 'Group by commerce rail',
  },
  channelTableColumns: {
    verifiedRevenue: 'Verified revenue',
    discrepancyRate: 'Discrepancy rate',
    revenueReliability: 'Revenue Reliability',
    policyAuthority: 'Policy authority',
    benchmarkContext: 'Benchmark context',
  },
  recentEnvelopes: 'Recent TrustEnvelopes',
  recentEnvelopesPager: {
    label: 'Browse recent TrustEnvelopes pages',
    previous: 'Show newer TrustEnvelopes',
    next: 'Show older TrustEnvelopes',
    pageStatus: (start: number, end: number, total: number) => `${start}–${end} of ${total}`,
  },
  recentEnvelopeTableColumns: {
    subjectRef: 'Subject reference',
    verifiedRevenue: 'Verified revenue',
    matchVerdict: 'Verdict',
    policyAuthority: 'Policy authority',
    trustSignal: 'Trust signal',
  },
  envelopeTableColumns: {
    envelopeId: 'Envelope ID',
    subject: 'Subject',
    status: 'Status',
    created: 'Created',
    authority: 'Authority',
    auditReference: 'Audit reference',
  },
  auditActivity: 'Vault log',
  viewAuditLedger: 'View Audit Ledger',
  auditStripEmpty: 'No signed audit actions in the current window.',
  auditStripCaption: 'Signed audit actions, newest first',
  auditStripColumns: {
    timestamp: 'Timestamp',
    actor: 'Actor',
    action: 'Action',
    target: 'Target',
  },
  openAuditEntry: 'Open',
  openAuditEntryAria: (action: string, target: string) => `Open audit entry: ${action} for ${target}`,
  onboardingContinuationTitle: 'No TrustEnvelope generated yet',
  onboardingContinuationBody:
    'Connect commerce truth and complete onboarding to generate your first deterministic TrustEnvelope.',
  onboardingContinuationAction: 'Continue onboarding',
  trendEmptyTitle: 'No verified revenue trend yet',
  trendEmptyBody:
    'Connect a commerce source or wait for verified commerce events to build a deterministic trend.',
  trendEmptyAction: 'Connect commerce source',
  trendNoEventsBody:
    'No verified commerce events have arrived yet. Deterministic verification remains active on source ledgers.',
  summaryRowTitle: 'Trust state summary',
  loadingProgress: 'Still loading verified trust state…',
  retryAggregate: 'Retry loading Overview',
  integrationDegradedExplanation:
    'One or more integrations require attention. Review integration health before trusting aggregate summaries.',
  emptyTenant: 'Workspace required before Overview can load tenant-scoped aggregates.',
  confidenceDegradedBanner:
    'Confidence degraded. Probabilistic confidence may be delayed or unavailable. Deterministic verification remains active.',
  integrationAttentionBanner:
    'Integration attention needed. Review connection health before trusting aggregate summaries.',
  viewerReadOnlySupervisory:
    'Read-only access. Supervisory actions require owner, admin, or manager role.',
  viewSourceEvidence: 'View source evidence',
  benchmarkTransitionExplanation:
    'Benchmark source changed for this segment. Review before approving channel actions.',
  priorityIssues: {
    metaBudgetTitle: 'Pending certification for Meta budget increase',
    metaBudgetExplanation:
      'A proposed +14.8% budget change exceeds tenant policy. Awaiting certification by Finance Approver. Simulation is ready—notification sent.',
    metaBudgetAction: 'Review simulation',
    googleDiscrepancyTitle: 'Google Ads revenue mismatch exceeds 10% threshold',
    googleDiscrepancyExplanation:
      'Google Ads reported $48,920. Shopify verified $40,120. Difference exceeds tenant threshold.',
    googleDiscrepancyAction: 'Review claim',
    tiktokConfidenceTitle: 'Confidence unavailable for TikTok audience shift request',
    tiktokConfidenceExplanation:
      'A budget simulation is blocked because confidence is unavailable. Deterministic verification remains active.',
    tiktokConfidenceAction: 'Review confidence',
    linkedinBenchmarkTitle: 'LinkedIn benchmark source transition is in progress',
    linkedinBenchmarkAction: 'Inspect benchmark',
  },
  summaryDrilldown: {
    verified_revenue: { label: 'Open revenue details', href: '/app/claims?verificationStatus=verified' },
    claims_reconciled: { label: 'View unmatched claims', href: '/app/claims?verificationStatus=unverified' },
    action_authority_budget: { label: 'Review pending proposals', href: '/app/budget' },
    action_authority_policy: { label: 'Review authority rules', href: '/app/settings/policy' },
    open_exceptions: { label: 'Review blocking issues', href: '/app/exceptions' },
  },
  summaryLabels: {
    verified_revenue: 'Verified revenue',
    claims_reconciled: 'Claims reconciled',
    action_authority: 'Action authority',
    open_exceptions: 'Open exceptions',
  },
  summaryFinancial: {
    commerceBacked: 'Commerce-backed aggregate',
    ofConnectedCommerceRevenue: 'Of connected commerce revenue',
    awaitingCommerceEvents: 'Awaiting commerce events',
    awaitingTrendWindow: 'Awaiting prior-period comparison window',
  },
  summaryActionAuthority: {
    pendingApprovals: (count: number) =>
      `${count} Pending Certification${count === 1 ? '' : 's'}`,
    systemStateSimulationOnly: 'System State: Simulation Only',
    simulationOnlySubLabel: 'Automated actions are paused. Generate manual proposals.',
    systemStateBlocked: 'System State: Blocked',
    killSwitchSubLabel: 'Trust API paused. Review policy authority before acting.',
  },
  summaryTrustIssues: {
    zeroTrustIssues: '0 Trust Issues',
    criticalDiscrepancies: (count: number) =>
      `${count} Critical Discrepanc${count === 1 ? 'y' : 'ies'}`,
  },
  platformClaimLabel: 'Platform claim',
  trendDataUnavailableLabel: 'Data Unavailable',
  trendDataUnavailableChartLabel: 'Unavailable',
  trendDrillBreadcrumb: {
    commandCenter: 'Command Center',
    trend: 'Trend',
  },
  trendTooltipSource: (field: string, minor: bigint) => `Source: ${field} (${minor.toString()})`,
} as const;
