export const CLAIMS_LEDGER_PAGE_COPY = {
  title: 'Revenue Claims',
  subtitle: 'Platform claims reconciled against commerce and payment evidence.',
  exportAction: 'Export verified report',
  exportConfirmation:
    'This creates an externally shareable verified report for the current filtered ledger view. No new financial truth is created.',
  table: {
    sectionTitle: 'Revenue claims',
    caption:
      'Forensic line-item ledger: one immutable claim per row. Claim source (platform), campaign class, and commerce rail are separate dimensions. Verified and claimed revenue, difference, match verdict, attribution, confidence, policy authority, and audit actions.',
    updating: 'Updating claim results…',
    paginationRange: (start: number, end: number, total: number) => `${start}–${end} of ${total}`,
  },
} as const;

/** B2.4 reason-coded confidence column — interval or cause label; color carries disposition. */
export const CLAIMS_CONFIDENCE_LEDGER_COPY = {
  availableIntervalShort: (interval: string) => interval,
  coldStartShort: 'Cold start',
  insufficientDataShort: 'Insufficient data',
  workerFailureShort: 'Worker failure',
  computationTimeoutShort: 'Timeout',
  refitLockedShort: 'Refit locked',
  delayedShort: 'Delayed',
  unavailableOtherShort: 'Unavailable',
  availableExactTitle: (interval: string, method?: string) =>
    `Tight posterior ${interval}. Tenant-scoped Bayesian fit${method ? ` (${method})` : ''}. Deterministic verification remains active.`,
  availableStableTitle: (interval: string, method?: string, qualitative?: string) =>
    `Posterior ${interval}${method ? ` · ${method}` : ''}${qualitative ? ` · ${qualitative}` : ''}. Interval is artifact-backed; not a dashboard label. Deterministic verification remains active.`,
  availableWideTitle: (interval: string, context?: string) =>
    `Posterior ${interval}${context ? ` — ${context}` : ''}. Model disagreement or sparse fit; triage before treating as verified confidence. Deterministic verification remains active.`,
  coldStartTitle: (reason?: string) =>
    `Expected cold start — insufficient tenant history${reason ? ` (${reason})` : ''}. Not a worker failure. Deterministic verification remains active.`,
  insufficientDataTitle: (reason?: string) =>
    `Insufficient data for Bayesian projection${reason ? ` (${reason})` : ''}. Deterministic verification remains active.`,
  workerFailureTitle: (reason?: string) =>
    `Bayesian worker failure — may need intervention${reason ? ` (${reason})` : ''}. Deterministic verification remains active.`,
  computationTimeoutTitle: (reason?: string) =>
    `Computation timed out before posterior converged${reason ? ` (${reason})` : ''}. Deterministic verification remains active.`,
  refitLockedTitle: (reason?: string) =>
    `Refit locked — eligibility backoff active${reason ? ` (${reason})` : ''}. Deterministic verification remains active.`,
  delayedTitle: (reason?: string) =>
    `Bayesian computation delayed${reason ? ` (${reason})` : ''}. Deterministic verification remains active.`,
  unavailableOtherTitle: (reason?: string) =>
    reason ??
    'Confidence unavailable. Deterministic verification remains active.',
} as const;
