import type { DateRangeValue, PlatformType } from "./channel";
import type { ConfidenceLevel } from "./dashboard";

export interface ComparisonChannelData {
  channel: {
    id: string;
    name: string;
    platform_type: PlatformType;
  };
  dateRange: {
    start: string;
    end: string;
  };
  performance: {
    revenue: number;
    spend: number;
    roas: number;
    conversions: number;
  };
  confidenceRange: {
    low: number;
    high: number;
    level: ConfidenceLevel;
    explanation: string;
  };
  trendData: Array<{
    date: string;
    revenue: number;
    spend: number;
    roas: number;
    roasRangeLow: number;
    roasRangeHigh: number;
  }>;
}

export interface AvailableChannel {
  id: string;
  name: string;
  platform_type: PlatformType;
}

export interface WinnerDeclaration {
  channelId: string;
  channelName: string;
  roas: number;
  delta: number;
}

export interface BudgetRecommendation {
  fromChannelId: string;
  fromChannelName: string;
  toChannelId: string;
  toChannelName: string;
  shiftAmount: number;
  expectedRevenueIncrease: number;
  confidence: ConfidenceLevel;
}

export interface ComparisonPanelError {
  message: string;
  correlationId: string | null;
}

export type ComparisonScenario =
  | "default"
  | "no_winner"
  | "three_channels"
  | "four_channels"
  | "empty"
  | "loading"
  | "error";

export interface ComparisonViewModel {
  selectedChannelIds: string[];
  channelData: Record<string, ComparisonChannelData>;
  loading: Record<string, boolean>;
  errors: Record<string, ComparisonPanelError | null>;
  availableChannels: AvailableChannel[];
  dateRange: DateRangeValue;
  winner: WinnerDeclaration | null;
  budgetRecommendation: BudgetRecommendation | null;
}

export type ChannelComparisonUiState =
  | "populated"
  | "loading"
  | "empty"
  | "error_panel"
  | "error_global";

export type ChannelComparisonValidationGateKey =
  | "spatial"
  | "typography"
  | "logos"
  | "color"
  | "confidence"
  | "deltaLabels"
  | "states"
  | "accessibility"
  | "responsiveness"
  | "dataContract";

export interface ChannelComparisonValidationGateResult {
  key: ChannelComparisonValidationGateKey;
  label: string;
  pass: boolean;
  evidence: string;
}

export interface ChannelComparisonVariantManifest {
  agentId: "A" | "B" | "C" | "D" | "E";
  hypothesis: string;
  keyDecisions: string[];
  specInterpretations: string[];
  validation: ChannelComparisonValidationGateResult[];
}

export interface ChannelComparisonDerivedMetric {
  channelId: string;
  isBestByRoas: boolean;
  isBestByRevenue: boolean;
  revenueDeltaLabel: string | null;
  roasDeltaLabel: string | null;
  conversionDeltaLabel: string | null;
}

export interface ChannelComparisonViewState {
  selectedChannelIds: string[];
  dateRange: DateRangeValue;
  availableChannels: AvailableChannel[];
  availableChannelsError: ComparisonPanelError | null;
  channelData: Record<string, ComparisonChannelData>;
  loading: Record<string, boolean>;
  errors: Record<string, ComparisonPanelError | null>;
  winner: WinnerDeclaration | null;
  budgetRecommendation: BudgetRecommendation | null;
  derivedByChannelId: Record<string, ChannelComparisonDerivedMetric>;
}

export interface ChannelComparisonRendererProps {
  state: ChannelComparisonViewState;
  onAddChannel: (channelId: string) => void;
  onAddManualChannel: (channelId: string) => void;
  onRemoveChannel: (channelId: string) => void;
  onRetryChannel: (channelId: string) => void;
  onRetryGlobal: () => void;
  onDateRangeChange: (range: DateRangeValue) => void;
}
