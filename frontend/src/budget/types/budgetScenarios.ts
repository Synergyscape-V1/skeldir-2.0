export type ScenarioStatus =
  | 'draft'
  | 'processing'
  | 'completed'
  | 'applied'
  | 'rejected'
  | 'failed';

export type OptimizationGoal =
  | 'maximize_revenue'
  | 'maximize_roas'
  | 'minimize_cac';

export type DateRangeValue = 'last_30_days' | 'last_60_days' | 'last_90_days' | 'custom';

export interface OptimizationConstraints {
  keepTotalSpendWithinPercent?: number;
  maxChannelReductionPercent?: number;
  minimumChannelSpend?: number;
  preventChannelShutdown?: boolean;
}

export interface ScenarioProgressStep {
  label: string;
  status: 'complete' | 'current' | 'pending';
}

export interface ScenarioProgress {
  percentage: number;
  currentStep: string;
  steps: ScenarioProgressStep[];
  timeRemaining: number;
  startedAt: string;
}

export interface ScenarioSummary {
  description: string;
  expectedImpact: {
    revenue: number;
    revenuePercent: number;
    roas: number;
    roasDelta: number;
  };
  confidence: 'high' | 'medium' | 'low';
}

export interface ProposedChangeRow {
  channelId: string;
  channelName: string;
  currentSpend: number;
  proposedSpend: number;
  change: number;
  changePercent: number;
  expectedRoas: number | null;
  confidenceRange?: {
    low: number;
    high: number;
  };
}

export interface ScenarioAudit {
  transactionCount: number;
  verifiedRevenue: number;
  attributionModelId: string;
  confidenceExplanation: string;
  sqlPreview: string;
  auditTrailHref: string;
}

export interface AppliedStatus {
  appliedAt: string;
  appliedBy?: { id: string; name: string };
  platformStatus: Array<{
    platform: string;
    status: 'success' | 'pending' | 'failed';
    message?: string;
    updatedAt?: string;
  }>;
}

export interface RejectedStatus {
  rejectedAt: string;
  rejectedReason?: string;
}

export interface BudgetScenario {
  id: string;
  name: string | null;
  status: ScenarioStatus;
  createdAt: string;
  updatedAt: string;
  dateRange: {
    start?: string;
    end?: string;
    label: string;
    value: DateRangeValue;
  };
  model: 'bayesian_mmm';
  goal: OptimizationGoal;
  constraints: OptimizationConstraints;
  progress?: ScenarioProgress;
  summary?: ScenarioSummary;
  proposedChanges?: ProposedChangeRow[];
  strategicContext?: string;
  audit?: ScenarioAudit;
  llmCost: number;
  processingTimeMs?: number;
  appliedStatus?: AppliedStatus;
  rejectedStatus?: RejectedStatus;
  error?: {
    title: string;
    description: string;
    reason: string;
    correlationId: string | null;
  };
}

export interface ScenarioStats {
  activeCount: number;
  activeTrend: number;
  appliedThisMonth: number;
  appliedTrend: number;
  avgRevenueLift: number;
  revenueLiftTrend: number;
  totalBudgetOptimized: number;
}
