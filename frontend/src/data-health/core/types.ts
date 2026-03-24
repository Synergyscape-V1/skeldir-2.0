export type HealthStatus = "healthy" | "warning" | "critical";

export type MetricStatus = "good" | "warning" | "critical";

export interface ResourceLink {
  text: string;
  url: string;
}

export interface FixStep {
  stepNumber: number;
  instruction: string;
  codeSnippet?: string;
  resourceLink?: ResourceLink;
}

export interface FixGuide {
  steps: FixStep[];
}

export interface DataIssue {
  id: string;
  severity: "critical" | "warning" | "info";
  title: string;
  description: string;
  detectedAt: Date;
  affectedEntity: string;
  fixGuide?: FixGuide;
  resolvedAt?: Date | null;
}

export interface DataHealthData {
  overallScore: number;
  status: HealthStatus;
  lastUpdated: Date;
  trackingCoverage: number;
  utmConsistency: number;
  revenueMatchRate: number;
  issues: DataIssue[];
}

export interface DataHealthResponse {
  tracking_coverage: number;
  utm_consistency: number;
  revenue_match_rate: number;
  issues: Array<{
    id: string;
    severity: "critical" | "warning" | "info";
    title: string;
    description: string;
    detected_at: string;
    affected_entity: string;
    fix_guide?: {
      steps: Array<{
        step_number: number;
        instruction: string;
        code_snippet?: string;
        resource_link?: {
          text: string;
          url: string;
        };
      }>;
    } | null;
    resolved_at?: string | null;
  }>;
  last_updated: string;
}

export type DataHealthState =
  | { type: "initial_loading" }
  | { type: "error"; error: Error }
  | { type: "no_data" }
  | { type: "steady"; data: DataHealthData; stale: boolean };

export type DataHealthScenario = "good" | "warning" | "critical";

export type DataHealthUiState = "initial_loading" | "error" | "no_data" | "steady";

export interface DataHealthRendererProps {
  state: DataHealthState;
  scenario: DataHealthScenario;
  onRefresh: () => Promise<void> | void;
  onNavigateToIntegrations: () => void;
  onRetry: () => Promise<void> | void;
}
