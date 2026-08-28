import type { ExceptionCategory, ExceptionSeverity } from '../ledger/types';
import { POLICY_AUTHORITY_UI_LABELS } from '../lib/policyAuthorityLabels';

export const EXCEPTIONS_PAGE_COPY = {
  title: 'Exceptions',
  subtitle: 'Human-meaningful trust exceptions routed for review.',
  summary: {
    openExceptions: 'Open exceptions',
    policyApprovalsRequired: 'Pending certifications',
    signatureFailures: 'Signature failures',
    integrationRepairsNeeded: 'Integration repairs needed',
    ariaLabel: 'Exception queue summary',
  },
  categoryTabs: {
    ariaLabel: 'Exception category filters',
    all: 'All',
  },
  filters: {
    dateRange: 'Date range',
    category: 'Category',
    severity: 'Severity',
    status: 'Status',
    policyAuthority: 'Policy authority',
    sourceObject: 'Source object',
    searchPlaceholder: 'Search exception summary, object, or audit reference',
    clearFilters: 'Clear filters',
    all: 'All',
  },
  table: {
    caption: 'Human-meaningful trust exceptions',
    sectionTitle: 'Exception queue',
    severity: 'Severity',
    category: 'Category',
    summary: 'Exception summary',
    affectedObject: 'Affected object',
    policyAuthority: 'Policy authority',
    lastAuditEvent: 'Last audit event',
    createdAge: 'Created / age',
    status: 'Status',
    action: 'Action',
    review: 'Review',
    open: 'Open',
    statusOpen: 'Open',
    loadingProgress: 'Still loading exception queue…',
    updating: 'Updating exception results…',
    empty: 'No human-meaningful exceptions are routed for review.',
    filteredEmpty: 'No exceptions match the current filters.',
    moreActions: 'More actions',
  },
  pagination: {
    range: (start: number, end: number, total: number) =>
      `Showing ${start} to ${end} of ${total} exceptions`,
    first: 'First page',
    previous: 'Previous page',
    next: 'Next page',
    last: 'Last page',
    page: (page: number) => `Page ${page}`,
  },
} as const;

export const EXCEPTION_CATEGORY_LABELS: Record<ExceptionCategory, string> = {
  discrepancy_review: 'Discrepancy review',
  policy_approval_required: 'Pending Certification',
  signature_verification_failure: 'Signature verification failure',
  benchmark_source_transition: 'Benchmark source transition',
  agent_access_denied: 'Agent access denied',
  integration_repair_needed: 'Integration repair needed',
};

export const EXCEPTION_SEVERITY_LABELS: Record<ExceptionSeverity, string> = {
  critical: 'Critical',
  warning: 'Warning',
  info: 'Info',
};

export const EXCEPTION_STATUS_LABELS: Record<
  'open' | 'acknowledged' | 'suppressed' | 'resolved',
  string
> = {
  open: 'Open',
  acknowledged: 'Acknowledged',
  suppressed: 'Suppressed',
  resolved: 'Resolved',
};

export const EXCEPTION_POLICY_FILTER_LABELS = POLICY_AUTHORITY_UI_LABELS;

export const EXCEPTION_SOURCE_OBJECT_OPTIONS = [
  { value: 'campaign_group', label: 'Campaign group' },
  { value: 'trust_envelope', label: 'TrustEnvelope' },
  { value: 'channel', label: 'Channel' },
  { value: 'segment', label: 'Segment' },
  { value: 'agent', label: 'Agent' },
  { value: 'claim', label: 'Claim' },
] as const;

export const EXCEPTION_DETAIL_DRAWER_COPY = {
  titlePrimary: 'Exception',
  title: (exceptionId: string) => `Exception #${formatShortExceptionRef(exceptionId)}`,
  titleFallback: 'Exception detail',
  loading: 'Loading exception context…',
  severity: 'Severity',
  category: 'Category',
  affectedObject: 'Affected object',
  reviewState: 'Review state',
  auditReference: 'Audit reference',
  recommendedNextReview: 'Recommended next review',
  actions: 'Exception actions',
} as const;

/** Footnote-scale id segment — mirrors claim detail titleRef short-ref DNA. */
export function formatShortExceptionRef(exceptionId: string): string {
  const segment = exceptionId.split('_').pop() ?? exceptionId;
  return segment.length > 4 ? segment.slice(-4) : segment;
}

/** Humanize backend snake_case labels without inventing new enum values. */
export function formatExceptionDetailToken(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
