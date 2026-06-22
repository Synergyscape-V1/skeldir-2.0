// Illustrative data matching the reference design exactly
// "Q4 Growth & Max Reach (Illustrative)" scenario

import type { ChannelLogoId } from './ChannelLogos';

export const SCENARIO = {
  id: 'scenario-q4-growth',
  name: 'Q4 Growth & Max Reach',
  subtitle: '(Illustrative)',
  status: 'active' as const,
  confidenceLabel: 'Moderate confidence',
  actionImplication: 'Monitor for 1-2 more weeks',
  /** Reference example: $50k total with allocation split per Budget Scenario Detail spec */
  proposedTotalBudget: '$50,000',
  projectedTotalRevenue: '$18.2M',
  projectedROI: '5.2x',
  isVerified: true,
  modelGeneratedAt: '2026-03-15T14:22:00Z',
  createdAt: '2026-03-01',
  lastRun: '2026-03-05 14:22',
};

/** Row definition for the Scenario Parameter Matrix (allocation sandbox). */
export interface MatrixChannelRow {
  id: string;
  name: string;
  logo: ChannelLogoId;
  /** Default allocation % (documentation example totals 100%). */
  defaultPercent: number;
}

/**
 * Reference example: total budget $50,000.
 * Spec lists Facebook 30% — UI uses Meta + Meta Ads icon for that row.
 * | Facebook | 30% | $15,000 | …
 */
export const MATRIX_CHANNEL_ROWS: MatrixChannelRow[] = [
  { id: 'meta', name: 'Meta', logo: 'meta', defaultPercent: 30 },
  { id: 'google-ads', name: 'Google', logo: 'google', defaultPercent: 40 },
  { id: 'linkedin', name: 'LinkedIn', logo: 'linkedin', defaultPercent: 20 },
  { id: 'tiktok', name: 'TikTok', logo: 'tiktok', defaultPercent: 10 },
];

export const MATRIX_SCENARIO_OPTIONS = [
  'Q2 Aggressive',
  'Q2 Cautious',
  'Q3 Test',
  "Holiday '25",
  'Q4 Growth & Max Reach',
  'Baseline Q3',
  'New scenario',
] as const;

export const MATRIX_MODEL_OPTIONS = ['Bayesian', 'Linear', 'Time-Decay'] as const;

export const MATRIX_HORIZON_OPTIONS = ['30 days', '60 days', '90 days', 'Custom'] as const;

/** Default matrix state aligned with documentation ($50k, 30/40/20/10). */
export const MATRIX_DEFAULT_TOTAL_BUDGET = 50_000;

export function matrixInitialPercents(): Record<string, number> {
  return Object.fromEntries(MATRIX_CHANNEL_ROWS.map((r) => [r.id, r.defaultPercent]));
}

/** Matrix snapshot — shared by Parameter Matrix, scenario tabs, and future fan-chart binding. */
export interface MatrixParametersSnapshot {
  scenarioName: string;
  totalBudget: number;
  percents: Record<string, number>;
  model: string;
  horizon: string;
}

function cloneSnapshot(s: MatrixParametersSnapshot): MatrixParametersSnapshot {
  return { ...s, percents: { ...s.percents } };
}

export function defaultMatrixSnapshot(scenarioName: string): MatrixParametersSnapshot {
  return {
    scenarioName,
    totalBudget: MATRIX_DEFAULT_TOTAL_BUDGET,
    percents: matrixInitialPercents(),
    model: 'Bayesian',
    horizon: '90 days',
  };
}

/** Equal split across channels (for “New scenario”). */
export function equalAllocationMatrixSnapshot(scenarioName: string): MatrixParametersSnapshot {
  const n = MATRIX_CHANNEL_ROWS.length;
  const each = 100 / n;
  const percents = Object.fromEntries(MATRIX_CHANNEL_ROWS.map((r) => [r.id, each]));
  return {
    scenarioName,
    totalBudget: MATRIX_DEFAULT_TOTAL_BUDGET,
    percents,
    model: 'Bayesian',
    horizon: '90 days',
  };
}

export interface BudgetScenarioTab {
  id: string;
  name: string;
  draft: MatrixParametersSnapshot;
  saved: MatrixParametersSnapshot;
}

export function createBudgetScenarioTab(
  id: string,
  name: string,
  snapshot: MatrixParametersSnapshot
): BudgetScenarioTab {
  const d = cloneSnapshot(snapshot);
  return { id, name, draft: d, saved: cloneSnapshot(d) };
}

/** Spec: max 5 saved scenario tabs (+ New Scenario control). */
export const MAX_SCENARIO_TABS = 5;

/** Initial rail tabs (documentation-style names; varied snapshots for comparison). */
export const INITIAL_BUDGET_SCENARIO_TABS: BudgetScenarioTab[] = [
  createBudgetScenarioTab('tab-q2-agg', 'Q2 Aggressive', defaultMatrixSnapshot('Q2 Aggressive')),
  createBudgetScenarioTab('tab-q2-caut', 'Q2 Cautious', {
    ...defaultMatrixSnapshot('Q2 Cautious'),
    percents: { meta: 25, 'google-ads': 35, linkedin: 25, tiktok: 15 },
    model: 'Linear',
  }),
  createBudgetScenarioTab('tab-q3-test', 'Q3 Test', {
    ...defaultMatrixSnapshot('Q3 Test'),
    totalBudget: 45_000,
    percents: { meta: 28, 'google-ads': 38, linkedin: 22, tiktok: 12 },
  }),
  createBudgetScenarioTab('tab-holiday', "Holiday '25", {
    ...defaultMatrixSnapshot("Holiday '25"),
    totalBudget: 60_000,
    horizon: '60 days',
    percents: { meta: 32, 'google-ads': 33, linkedin: 20, tiktok: 15 },
  }),
];

/** Values are **thousands USD** (monthly revenue $K) for the fan chart Y-axis. */
export interface ChartDataPoint {
  x: string;
  /** Tooltip / screen reader: e.g. "March 2026" */
  tooltipDate?: string;
  hist: number | null;
  med: number | null;
  ciLow: number | null;
  ciHigh: number | null;
}

/** Labels prefixed with '_' are hidden on the x-axis (Recharts categorical keys). */
export const VISIBLE_LABELS = new Set(['Jan', 'Feb', 'Mar', 'Today', 'Apr', 'May', 'Jun']);

/**
 * Illustrative monthly series (Jan–Jun) — API would supply this; values in $K.
 * Skeldir spec: monthly granularity, fan widens after Today.
 */
export const CHART_DATA: ChartDataPoint[] = [
  { x: 'Jan', tooltipDate: 'January 2026', hist: 28, med: null, ciLow: null, ciHigh: null },
  { x: 'Feb', tooltipDate: 'February 2026', hist: 32, med: null, ciLow: null, ciHigh: null },
  { x: 'Mar', tooltipDate: 'March 2026', hist: 38, med: null, ciLow: null, ciHigh: null },
  { x: '_h1', tooltipDate: 'March 2026', hist: 39, med: null, ciLow: null, ciHigh: null },
  { x: 'Today', tooltipDate: 'March 2026', hist: 40, med: 40, ciLow: 40, ciHigh: 40 },
  { x: 'Apr', tooltipDate: 'April 2026', hist: null, med: 48, ciLow: 36, ciHigh: 62 },
  { x: '_p1', tooltipDate: 'April 2026', hist: null, med: 50, ciLow: 35, ciHigh: 66 },
  { x: 'May', tooltipDate: 'May 2026', hist: null, med: 52, ciLow: 34, ciHigh: 70 },
  { x: '_p2', tooltipDate: 'May 2026', hist: null, med: 54, ciLow: 33, ciHigh: 74 },
  { x: 'Jun', tooltipDate: 'June 2026', hist: null, med: 56, ciLow: 32, ciHigh: 78 },
];

export interface ComparisonScenario {
  id: string;
  name: string;
  status: string;
  statusLabel: string;
  proposedBudget: string;
  projectedRevenue: string;
  projectedROI: string;
  confidence: 'high' | 'medium' | 'low';
  confidenceLabel: string;
  actions: string[];
  isActive: boolean;
}

export const COMPARISON_SCENARIOS: ComparisonScenario[] = [
  {
    id: 'active',
    name: 'Q4 Growth & Max Reach',
    status: 'active',
    statusLabel: 'Active',
    proposedBudget: '$3.5M',
    projectedRevenue: '$18.2M',
    projectedROI: '5.2x',
    confidence: 'medium',
    confidenceLabel: 'Moderate confidence',
    actions: ['Review & Approve'],
    isActive: true,
  },
  {
    id: 'archived-baseline',
    name: 'Baseline Q3',
    status: 'archived',
    statusLabel: 'Archived',
    proposedBudget: '$3.5M',
    projectedRevenue: '$18.2M',
    projectedROI: '5.2x',
    confidence: 'high',
    confidenceLabel: 'High confidence',
    actions: ['Approve Changes', 'Reject'],
    isActive: false,
  },
  {
    id: 'archived-conservative',
    name: 'Conservative',
    status: 'archived',
    statusLabel: 'Archived',
    proposedBudget: '$3.5M',
    projectedRevenue: '$18.2M',
    projectedROI: '5.2x',
    confidence: 'high',
    confidenceLabel: 'High confidence',
    actions: ['Approve Changes', 'Reject'],
    isActive: false,
  },
];
