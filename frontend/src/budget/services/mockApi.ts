import {
  BudgetScenario,
  OptimizationGoal,
  DateRangeValue,
  OptimizationConstraints,
  ScenarioStats,
} from '../types/budgetScenarios';

const MOCK_SCENARIOS: BudgetScenario[] = [
  {
    id: 'scn_2023_a3f7',
    name: 'Q1 Budget Reallocation',
    status: 'completed',
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    updatedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    dateRange: {
      value: 'last_30_days',
      label: 'Last 30 Days',
      start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
      end: new Date().toISOString(),
    },
    model: 'bayesian_mmm',
    goal: 'maximize_revenue',
    constraints: { keepTotalSpendWithinPercent: 10, maxChannelReductionPercent: 20 },
    llmCost: 0.12,
    summary: {
      description:
        'Shift $8,000 from Pinterest to Google Search to capture high-intent demand.',
      expectedImpact: {
        revenue: 2400000,
        revenuePercent: 8.5,
        roas: 3.62,
        roasDelta: 0.42,
      },
      confidence: 'medium',
    },
    proposedChanges: [
      {
        channelId: 'google_ads',
        channelName: 'Google Ads',
        currentSpend: 4500000,
        proposedSpend: 5300000,
        change: 800000,
        changePercent: 17.7,
        expectedRoas: 4.1,
        confidenceRange: { low: 3.8, high: 4.4 },
      },
      {
        channelId: 'pinterest_ads',
        channelName: 'Pinterest Ads',
        currentSpend: 1200000,
        proposedSpend: 400000,
        change: -800000,
        changePercent: -66.6,
        expectedRoas: 1.8,
        confidenceRange: { low: 1.2, high: 2.1 },
      },
      {
        channelId: 'facebook_ads',
        channelName: 'Facebook Ads',
        currentSpend: 3000000,
        proposedSpend: 3000000,
        change: 0,
        changePercent: 0,
        expectedRoas: 3.2,
        confidenceRange: { low: 2.9, high: 3.5 },
      },
    ],
    strategicContext:
      'Our Bayesian MMM model detected a diminishing return on Pinterest Ads spend beyond $4k/month. Meanwhile, Google Ads Search impression share suggests room for scale. By shifting this budget, we expect to capture ~150 additional conversions without increasing total burn.',
    audit: {
      transactionCount: 14502,
      verifiedRevenue: 84500000,
      attributionModelId: 'mdl_v4_bayesian',
      confidenceExplanation:
        'Based on 90 days of attribution data with 95% statistical significance.',
      sqlPreview:
        'SELECT channel, sum(spend) FROM marketing_spend WHERE date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)...',
      auditTrailHref: '#',
    },
  },
  {
    id: 'scn_2023_b9c2',
    name: 'Aggressive Growth',
    status: 'applied',
    createdAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    updatedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    dateRange: { value: 'last_90_days', label: 'Last 90 Days' },
    model: 'bayesian_mmm',
    goal: 'maximize_revenue',
    constraints: {},
    llmCost: 0.15,
    summary: {
      description: 'Increased budget by 20% focusing on TikTok and Instagram Reels.',
      expectedImpact: { revenue: 5600000, revenuePercent: 12.3, roas: 2.9, roasDelta: -0.2 },
      confidence: 'high',
    },
    appliedStatus: {
      appliedAt: new Date(Date.now() - 46 * 60 * 60 * 1000).toISOString(),
      platformStatus: [
        { platform: 'TikTok Ads', status: 'success' },
        { platform: 'Meta Ads', status: 'success' },
        { platform: 'Google Ads', status: 'success' },
      ],
    },
  },
  {
    id: 'scn_2023_proc1',
    name: 'Scenario A3F7',
    status: 'processing',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    dateRange: { value: 'last_30_days', label: 'Last 30 Days' },
    model: 'bayesian_mmm',
    goal: 'maximize_roas',
    constraints: {},
    llmCost: 0.08,
    progress: {
      percentage: 65,
      currentStep: 'Running linear programming optimization',
      steps: [
        { label: 'Validating data integrity', status: 'complete' },
        { label: 'Training Bayesian model', status: 'complete' },
        { label: 'Running linear programming optimization', status: 'current' },
        { label: 'Generating strategic analysis', status: 'pending' },
      ],
      timeRemaining: 18,
      startedAt: new Date().toISOString(),
    },
  },
];

const SCENARIO_STATS: ScenarioStats = {
  activeCount: 12,
  activeTrend: 0,
  appliedThisMonth: 8,
  appliedTrend: 0,
  avgRevenueLift: 12.3,
  revenueLiftTrend: 12.3,
  totalBudgetOptimized: 15600000,
};

let scenarios = [...MOCK_SCENARIOS];

export const mockApi = {
  getScenarios: async (): Promise<{ scenarios: BudgetScenario[]; stats: ScenarioStats }> => {
    await delay(600);
    return { scenarios: [...scenarios], stats: SCENARIO_STATS };
  },

  getScenarioById: async (id: string): Promise<BudgetScenario> => {
    await delay(400);
    const scenario = scenarios.find((s) => s.id === id);
    if (!scenario) throw new Error('Scenario not found');
    return { ...scenario };
  },

  createScenario: async (request: {
    dateRange: DateRangeValue;
    goal: OptimizationGoal;
    constraints: OptimizationConstraints;
  }): Promise<BudgetScenario> => {
    await delay(1000);
    const newId = `scn_${Date.now().toString(36)}`;
    const newScenario: BudgetScenario = {
      id: newId,
      name: `Scenario ${newId.slice(-4).toUpperCase()}`,
      status: 'processing',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      dateRange: { value: request.dateRange, label: request.dateRange.replace(/_/g, ' ') },
      model: 'bayesian_mmm',
      goal: request.goal,
      constraints: request.constraints,
      llmCost: 0.05,
      progress: {
        percentage: 0,
        currentStep: 'Initializing optimization engine...',
        steps: [
          { label: 'Validating data integrity', status: 'current' },
          { label: 'Training Bayesian model', status: 'pending' },
          { label: 'Running linear programming optimization', status: 'pending' },
          { label: 'Generating strategic analysis', status: 'pending' },
        ],
        timeRemaining: 60,
        startedAt: new Date().toISOString(),
      },
    };
    scenarios = [newScenario, ...scenarios];
    startProcessingSimulation(newId);
    return newScenario;
  },

  applyScenario: async (id: string): Promise<BudgetScenario> => {
    await delay(1500);
    const index = scenarios.findIndex((s) => s.id === id);
    if (index === -1) throw new Error('Scenario not found');
    scenarios[index] = {
      ...scenarios[index],
      status: 'applied',
      appliedStatus: {
        appliedAt: new Date().toISOString(),
        platformStatus: [
          { platform: 'Google Ads', status: 'pending' },
          { platform: 'Meta Ads', status: 'pending' },
        ],
      },
    };
    setTimeout(() => {
      const s = scenarios.find((s) => s.id === id);
      if (s?.appliedStatus) {
        s.appliedStatus.platformStatus.forEach((p) => (p.status = 'success'));
      }
    }, 5000);
    return { ...scenarios[index] };
  },

  rejectScenario: async (id: string): Promise<BudgetScenario> => {
    await delay(800);
    const index = scenarios.findIndex((s) => s.id === id);
    if (index === -1) throw new Error('Scenario not found');
    scenarios[index] = {
      ...scenarios[index],
      status: 'rejected',
      rejectedStatus: { rejectedAt: new Date().toISOString() },
    };
    return { ...scenarios[index] };
  },
};

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function startProcessingSimulation(id: string) {
  let progress = 0;
  const interval = setInterval(() => {
    const index = scenarios.findIndex((s) => s.id === id);
    if (index === -1) { clearInterval(interval); return; }
    progress += 1.6;
    const scenario = scenarios[index];
    if (!scenario.progress) return;
    scenario.progress.percentage = Math.min(100, progress);
    scenario.progress.timeRemaining = Math.max(0, 60 - progress * 0.6);
    if (progress > 15 && scenario.progress.steps[0].status !== 'complete') {
      scenario.progress.steps[0].status = 'complete';
      scenario.progress.steps[1].status = 'current';
      scenario.progress.currentStep = 'Training Bayesian model';
    }
    if (progress > 45 && scenario.progress.steps[1].status !== 'complete') {
      scenario.progress.steps[1].status = 'complete';
      scenario.progress.steps[2].status = 'current';
      scenario.progress.currentStep = 'Running linear programming optimization';
    }
    if (progress > 85 && scenario.progress.steps[2].status !== 'complete') {
      scenario.progress.steps[2].status = 'complete';
      scenario.progress.steps[3].status = 'current';
      scenario.progress.currentStep = 'Generating strategic analysis';
    }
    if (progress >= 100) {
      clearInterval(interval);
      scenarios[index] = {
        ...scenario,
        status: 'completed',
        progress: undefined,
        summary: {
          description: 'Optimization complete. Recommended shifting spend to maximize efficiency.',
          expectedImpact: { revenue: 1500000, revenuePercent: 5.2, roas: 3.8, roasDelta: 0.2 },
          confidence: 'high',
        },
        proposedChanges: [
          {
            channelId: 'google_ads', channelName: 'Google Ads',
            currentSpend: 2000000, proposedSpend: 2500000,
            change: 500000, changePercent: 25, expectedRoas: 4.0,
          },
          {
            channelId: 'facebook_ads', channelName: 'Facebook Ads',
            currentSpend: 2000000, proposedSpend: 1500000,
            change: -500000, changePercent: -25, expectedRoas: 3.0,
          },
        ],
        strategicContext:
          'The model identified that Facebook Ads has reached saturation for the current audience segment, while Google Ads retains elasticity. Reallocating budget captures more efficient demand.',
        audit: {
          transactionCount: 8500,
          verifiedRevenue: 45000000,
          attributionModelId: 'mdl_v4_bayesian',
          confidenceExplanation: 'High confidence due to consistent historical patterns.',
          sqlPreview: 'SELECT * FROM attribution_window WHERE...',
          auditTrailHref: '#',
        },
      };
    }
  }, 1000);
}
