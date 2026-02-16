/**
 * SKELDIR COPY SYSTEM
 *
 * All user-facing text for Skeldir UI surfaces.
 * Rules:
 *   1. Lead with outcome, append context
 *   2. Quantify everything that can be quantified
 *   3. Confidence terminology is a CLOSED vocabulary: High/Medium/Low only
 *   4. Never anthropomorphize: "The model shows" not "Skeldir thinks"
 *   5. Error messages always contain: what happened + why + exactly what to do
 *
 * No placeholder copy survives to production.
 * Every string marked TODO must be resolved before merge.
 */

// ─────────────────────────────────────────────────────────────────
// CONFIDENCE LABELS — closed vocabulary, no synonyms permitted
// ─────────────────────────────────────────────────────────────────

export const confidenceCopy = {
  high:   (margin: number) => `High Confidence · ±${margin}%`,
  medium: (margin: number) => `Medium Confidence · ±${margin}%`,
  low:    (margin: number) => `Low Confidence · ±${margin}% — more data needed`,
  explanations: {
    high:   (days: number, conversions: number) =>
      `Based on ${days} days of stable data and ${conversions.toLocaleString()} conversions with consistent patterns.`,
    medium: (days: number) =>
      `Based on ${days} days of data. Add ${14 - days > 0 ? 14 - days : 0} more days to increase confidence.`,
    low:    (days: number) =>
      `Only ${days} days of data available. Attribution ranges are wide until more evidence accumulates.`,
  },
} as const;

// ─────────────────────────────────────────────────────────────────
// DISCREPANCY LABELS
// ─────────────────────────────────────────────────────────────────

export const discrepancyCopy = {
  safe:     (percent: number) => `Within noise floor (±${Math.abs(percent).toFixed(1)}%)`,
  warning:  (percent: number, platform: string) =>
    `${Math.abs(percent).toFixed(1)}% discrepancy between ${platform} claims and verified revenue — review source data`,
  critical: (percent: number, platform: string, revenueSource: string) =>
    `${Math.abs(percent).toFixed(1)}% discrepancy: ${platform} claims ${percent > 0 ? 'more' : 'less'} than ${revenueSource} recorded — investigate before budget decisions`,
} as const;

// ─────────────────────────────────────────────────────────────────
// EMPTY STATES — specific to context, never generic
// ─────────────────────────────────────────────────────────────────

export const emptyStateCopy = {
  noDataYet: {
    commandCenter:  'Connect your first platform to begin attribution modeling.',
    channelTable:   'No channels connected. Connect at least one ad platform and a revenue source.',
    budgetOptimizer: 'Attribution data required before budget optimization. Connect platforms first.',
    dataHealth:     'No integrations configured. Add your first connection below.',
  },
  buildingModel: {
    commandCenter:  (currentDay: number) =>
      `Day ${currentDay} of 14 — accumulating evidence for your first model.`,
    channelTable:   (currentDay: number) =>
      `Building attribution model. ${14 - currentDay} days of data remaining.`,
  },
  noResultsFilter: {
    channelTable:   'No channels match this filter. Adjust date range or clear channel filters.',
    budgetScenarios: 'No saved scenarios match this filter.',
    investigations:  'No investigations match this status filter.',
  },
  featureLocked: {
    teamManagement: 'Team management is available on the Agency plan.',
    whiteLabel:     'White-label configuration is available on the Agency plan.',
    investigations: 'Investigation queue is available on Pro and Agency plans.',
  },
} as const;

// ─────────────────────────────────────────────────────────────────
// ERROR MESSAGES — what happened + why + what to do
// ─────────────────────────────────────────────────────────────────

export const errorCopy = {
  apiTimeout: (correlationId: string) => ({
    title:   'Dashboard timed out.',
    body:    'The attribution data request exceeded 30 seconds. Your data is intact.',
    action:  'Retry',
    support: `Report issue #${correlationId}`,
  }),

  oauthFailed: (platform: string) => ({
    title:   `Connection to ${platform} failed.`,
    body:    `Check that Skeldir has the required permissions in your ${platform} Business Account.`,
    primary: 'Try Again',
    secondary: 'Get Help',
  }),

  oauthExpired: (platform: string, daysUntilExpiry: number) => ({
    title:   `${platform} connection expires in ${daysUntilExpiry} days.`,
    body:    'Attribution will pause if not renewed.',
    action:  `Renew ${platform} Connection`,
  }),

  dataGap: (platform: string, dateRange: string) => ({
    title:   `${platform} data missing for ${dateRange}.`,
    body:    'Attribution confidence ranges for this period are wider than normal.',
    action:  'View Data Health',
  }),

  trackingTagMissing: (pagePercent: number) => ({
    title:   `Tracking tag missing on ${pagePercent}% of pages.`,
    body:    'Attribution accuracy is reduced. Install the tag on all pages.',
    action:  'View Setup Guide',
  }),

  insufficientData: (daysAvailable: number) => ({
    title:   `Only ${daysAvailable} days of data available.`,
    body:    `Attribution requires at least 14 days. Model will be ready in ${14 - daysAvailable} days.`,
    action:  null,
  }),
} as const;

// ─────────────────────────────────────────────────────────────────
// TOOLTIPS — hover/click explanations for every technical metric
// ─────────────────────────────────────────────────────────────────

export const tooltipCopy = {
  roas: (revenueSource: string) =>
    `Revenue attributed to this channel per $1 spent. Calculated using Bayesian posterior mean, verified against ${revenueSource} transactions.`,

  confidence: (days: number, conversionCount: number) =>
    `Model certainty based on ${days} days of data and ${conversionCount.toLocaleString()} conversions. High = ±10%, Medium = ±25%, Low = ±50%.`,

  discrepancy: (platform: string, revenueSource: string) =>
    `Difference between what ${platform} claims as revenue and what ${revenueSource} recorded in the same period. Discrepancies >15% require investigation.`,

  verifiedRevenue: (revenueSource: string) =>
    `Revenue confirmed in ${revenueSource} — Skeldir's ground truth. This number is not affected by ad platform reporting.`,

  attributedRevenue:
    'Revenue the model assigns to this channel based on its contribution to conversions, adjusted for multi-touch paths and time decay.',

  modelVersion:
    'Attribution models are rebuilt every 24 hours as new conversion data arrives. Version number increments with each rebuild.',

  confidenceInterval: (lower: string, upper: string) =>
    `The model is 90% confident the true ROAS falls between ${lower} and ${upper}. The displayed value is the posterior mean.`,
} as const;

// ─────────────────────────────────────────────────────────────────
// ACTIONS — CTA labels, precise and action-first
// ─────────────────────────────────────────────────────────────────

export const actionCopy = {
  primary: {
    connect:        (platform: string) => `Connect ${platform}`,
    approveBudget:  'Approve Budget Shift',
    viewAnalysis:   (channel: string) => `View ${channel} Analysis`,
    exportReport:   'Export Report',
    retryConnection: (platform: string) => `Retry ${platform}`,
    fixTrackingTag: 'Fix Tracking Tag',
    upgradeToAgency: 'Upgrade to Agency',
  },
  secondary: {
    whyThisRange:    'Why this range?',
    seeTransactions: (count: number) => `See ${count.toLocaleString()} transactions`,
    howAttribution:  'How attribution works',
    connectLater:    'Connect Later',
    viewDataHealth:  'View Data Health',
    reportIssue:     (correlationId: string) => `Report issue #${correlationId}`,
    learnMore:       'Learn more',
  },
  destructive: {
    disconnectPlatform: (platform: string) => ({
      label:       `Remove ${platform}`,
      confirmation: `Remove ${platform} connection? Attribution data for this channel will stop updating. Historical data is preserved.`,
      confirm:     `Remove ${platform}`,
      cancel:      'Keep Connection',
    }),
    deleteScenario: (scenarioName: string) => ({
      label:       `Delete Scenario`,
      confirmation: `Delete "${scenarioName}"? This cannot be undone.`,
      confirm:     'Delete Scenario',
      cancel:      'Cancel',
    }),
  },
} as const;

// ─────────────────────────────────────────────────────────────────
// METRIC LABELS — standard naming across all screens
// ─────────────────────────────────────────────────────────────────

export const metricLabels = {
  verifiedRoas:        'Verified ROAS',
  verifiedRevenue:     'Verified Revenue',
  attributedRevenue:   'Attributed Revenue',
  platformClaimed:     (platform: string) => `${platform} Claimed`,
  discrepancy:         'Revenue Discrepancy',
  adSpend:             'Ad Spend',
  cpa:                 'Cost Per Acquisition',
  ctr:                 'Click-Through Rate',
  conversionRate:      'Conversion Rate',
  modelConfidence:     'Model Confidence',
  dataFreshness:       'Data Freshness',
} as const;

// ─────────────────────────────────────────────────────────────────
// FORBIDDEN PATTERNS — test before merging any copy
// ─────────────────────────────────────────────────────────────────

export const FORBIDDEN_PATTERNS = [
  { pattern: /get started/i,           replacement: 'Use the specific first action (e.g., "Connect Facebook Ads")' },
  { pattern: /something went wrong/i,  replacement: 'State what specifically went wrong' },
  { pattern: /loading\.\.\./i,         replacement: 'State what is loading (e.g., "Loading attribution data...")' },
  { pattern: /no data found/i,         replacement: 'Explain why and what to do (see emptyStateCopy)' },
  { pattern: /invalid input/i,         replacement: 'State what is invalid and the correct format' },
  { pattern: /are you sure\?/i,        replacement: 'State the consequence (see actionCopy.destructive)' },
  { pattern: /skeldir thinks/i,        replacement: '"The model shows"' },
  { pattern: /ai thinks/i,             replacement: '"The model shows"' },
  { pattern: /probably/i,              replacement: 'Use confidence level: High/Medium/Low' },
  { pattern: /\blikely\b/i,            replacement: 'Use confidence level: High/Medium/Low' },
  { pattern: /we\'re working on it/i,  replacement: 'Provide specific ETA or current status' },
  { pattern: /please wait/i,           replacement: 'State what is happening (e.g., "Building attribution model...")' },
] as const;

/**
 * Audit copy string against forbidden patterns.
 * Run this in test suite for all UI strings.
 */
export function auditCopyString(copy: string): Array<{ pattern: string; replacement: string }> {
  return FORBIDDEN_PATTERNS
    .filter(({ pattern }) => pattern.test(copy))
    .map(({ pattern, replacement }) => ({
      pattern: pattern.toString(),
      replacement,
    }));
}
