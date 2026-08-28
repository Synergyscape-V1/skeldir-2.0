import { POLICY_AUTHORITY_EXPLANATION } from '../lib/policyAuthorityLabels';

export const LEDGER_COPY = {
  trustApiError: 'Trust API read failed. No financial truth was changed.',
  networkError: 'Network unavailable. Ledger data was not updated.',
  permissionDenied: 'You do not have permission to view this ledger.',
  scopeDenied: 'Agent scope does not permit this ledger surface.',
  policyUnavailable: 'Policy authority is unavailable. Actions remain blocked.',
  detailBlockedTitle: 'Detail view unavailable',
  detailBlockedBody: (surface: string) =>
    `${surface} detail opens in Level 8. This ledger preserves your current filters and position.`,
  detailBlockedAria: (surface: string) =>
    `${surface} detail is not available until Level 8. No financial truth was changed.`,
  futureActionDisabled: 'Actions open in Level 9',
  updatingResults: 'Updating results for the current query…',
  platformClaimLabel: 'Platform claim',
  verifiedRevenueLabel: 'Verified revenue',
  exportBlocked: 'Export verified report opens in Level 9',
  emptyClaims: 'No platform claims have arrived yet.',
  emptyClaimsFiltered: 'No claims match these filters.',
  emptyTrustIndex: 'No TrustEnvelopes generated yet.',
  emptyChannels: 'No channel trust data available.',
  emptyBenchmarks: 'No benchmark segments available.',
  emptyExceptions: 'No exceptions require review.',
  loadingProgress: 'Still loading ledger data…',
  paginationLabel: 'Ledger pagination',
  mobileDisclosureLabel: 'Show additional row fields',
  budgetBlockedSparse: POLICY_AUTHORITY_EXPLANATION.blockedSparse,
  budgetBlockedPolicy: 'Simulation unavailable by policy authority.',
} as const;
