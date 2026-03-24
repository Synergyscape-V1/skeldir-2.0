export type ConfidenceLevel = "high" | "medium" | "low";
export type ActionType = "error" | "warning" | "recommendation";
export type ActionVariant = "primary" | "secondary" | "tertiary";
export type ChannelSortField = "name" | "spend" | "revenue" | "roas";

export interface ActionButton {
  label: string;
  variant: ActionVariant;
  onClick?: () => void;
  href?: string;
}

export interface PriorityAction {
  id: string;
  type: ActionType;
  title: string;
  description: string;
  impact?: string;
  actions: ActionButton[];
}

export interface ChannelPerformance {
  id: string;
  name: string;
  spend: number;
  revenue: number;
  roas: number;
  confidence: ConfidenceLevel;
  confidence_range: {
    low: number;
    high: number;
  };
}

export interface DashboardData {
  totalRevenue: number;
  revenueChange: number;
  roas: number;
  roasConfidence: ConfidenceLevel;
  activeIssuesCount: number;
  priorityActions: PriorityAction[];
  channels: ChannelPerformance[];
  isEmpty: boolean;
}

export interface DashboardState {
  data: DashboardData | null;
  loading: boolean;
  error: {
    message: string;
    correlationId: string | null;
  } | null;
  lastUpdated: Date | null;
}

export type DashboardScenario =
  | "ready"
  | "loading"
  | "empty"
  | "error"
  | "polling_degraded";

export type DatasetVariant = "high" | "mixed" | "low";
