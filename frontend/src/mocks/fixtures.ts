import type {
  DashboardData,
  DashboardScenario,
  DatasetVariant,
  PriorityAction,
} from "../types/dashboard";

const baseActions: PriorityAction[] = [
  {
    id: "action_001",
    type: "error",
    title: "Meta Ads tracking missing on checkout pages",
    description: "Impact: 40% of conversions untracked",
    impact: "40% of conversions untracked",
    actions: [
      { label: "Fix Now", variant: "primary", href: "/data/integrations?issue=fb_tracking" },
      { label: "Learn More", variant: "secondary", href: "/docs/tracking-setup" },
    ],
  },
  {
    id: "action_002",
    type: "recommendation",
    title: "Shift $8K from Pinterest to Google Search",
    description: "Expected lift: +$24K revenue (Medium Confidence)",
    actions: [
      { label: "Review Recommendation", variant: "primary", href: "/budget/scenarios/247" },
      { label: "Apply Budget Change", variant: "secondary" },
    ],
  },
];

const mixed: DashboardData = {
  totalRevenue: 4384700,
  revenueChange: 12.3,
  roas: 3.2,
  roasConfidence: "high",
  activeIssuesCount: 2,
  priorityActions: baseActions,
  isEmpty: false,
  channels: [
    {
      id: "ch_google_ads",
      name: "Google Ads",
      spend: 1245000,
      revenue: 4820000,
      roas: 3.87,
      confidence: "high",
      confidence_range: { low: 3.65, high: 4.1 },
    },
    {
      id: "ch_meta_ads",
      name: "Meta Ads",
      spend: 890000,
      revenue: 2850000,
      roas: 3.2,
      confidence: "high",
      confidence_range: { low: 2.95, high: 3.45 },
    },
    {
      id: "ch_tiktok_ads",
      name: "TikTok Ads",
      spend: 320000,
      revenue: 680000,
      roas: 2.13,
      confidence: "medium",
      confidence_range: { low: 1.85, high: 2.4 },
    },
    {
      id: "ch_pinterest_ads",
      name: "Pinterest Ads",
      spend: 210000,
      revenue: 310000,
      roas: 1.48,
      confidence: "low",
      confidence_range: { low: 0.9, high: 2.1 },
    },
    {
      id: "ch_linkedin_ads",
      name: "LinkedIn Ads",
      spend: 450000,
      revenue: 1120000,
      roas: 2.49,
      confidence: "medium",
      confidence_range: { low: 2.1, high: 2.9 },
    },
  ],
};

const low: DashboardData = {
  ...mixed,
  revenueChange: -7.8,
  roas: 2.1,
  roasConfidence: "low",
  channels: mixed.channels.map((c) =>
    c.confidence === "high"
      ? { ...c, confidence: "medium", confidence_range: { low: c.roas - 1.2, high: c.roas + 1.2 } }
      : { ...c, confidence: "low", confidence_range: { low: Math.max(0.2, c.roas - 1.4), high: c.roas + 1.4 } }
  ),
};

const high: DashboardData = {
  ...mixed,
  revenueChange: 18.5,
  roas: 3.9,
  roasConfidence: "high",
  activeIssuesCount: 0,
  priorityActions: [],
  channels: mixed.channels.map((c) => ({
    ...c,
    roas: Math.max(3.1, c.roas + 0.7),
    confidence: "high",
    confidence_range: { low: c.roas + 0.5, high: c.roas + 0.8 },
  })),
};

export const datasetByVariant: Record<DatasetVariant, DashboardData> = {
  high,
  mixed,
  low,
};

export interface StoryHarnessState {
  scenario: DashboardScenario;
  data: DashboardData | null;
  loading: boolean;
  error: { message: string; correlationId: string | null } | null;
  staleBanner: boolean;
}

export const stateFixtures = {
  ready_mixed_confidence: getHarnessState("ready", "mixed"),
  ready_low_confidence_heavy: getHarnessState("ready", "low"),
  empty_under_14_days: getHarnessState("empty", "mixed"),
  error_initial_load: getHarnessState("error", "mixed"),
  stale_after_3_poll_failures: getHarnessState("polling_degraded", "mixed"),
};

export function getHarnessState(
  scenario: DashboardScenario,
  dataset: DatasetVariant = "mixed"
): StoryHarnessState {
  const data = datasetByVariant[dataset];
  switch (scenario) {
    case "loading":
      return { scenario, data: null, loading: true, error: null, staleBanner: false };
    case "error":
      return {
        scenario,
        data: null,
        loading: false,
        error: { message: "Failed to load dashboard data", correlationId: "corr-storybook-001" },
        staleBanner: false,
      };
    case "empty":
      return {
        scenario,
        data: { ...data, isEmpty: true, priorityActions: [], channels: [] },
        loading: false,
        error: null,
        staleBanner: false,
      };
    case "polling_degraded":
      return { scenario, data, loading: false, error: null, staleBanner: true };
    default:
      return { scenario: "ready", data, loading: false, error: null, staleBanner: false };
  }
}

export const requiredScenarios: DashboardScenario[] = [
  "ready",
  "loading",
  "empty",
  "error",
  "polling_degraded",
];
