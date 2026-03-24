export type FixGuidanceSeverity = "critical" | "caution" | "info";

export type FixIssueCategory =
  | "sync_stale"
  | "authentication_expired"
  | "rate_limited"
  | "webhook_missing"
  | "data_discrepancy"
  | "schema_drift";

export interface FixGuidanceIssue {
  category: FixIssueCategory;
  title: string;
  description: string;
}

export interface FixGuidanceImpact {
  description: string;
  affectedChannels?: string[];
  monetaryRisk?: string;
}

export type SecondaryActionType = "investigate" | "dismiss" | "defer";

export interface FixGuidanceRemediation {
  primary: {
    label: string;
    action: () => void;
    estimatedTime?: string;
  };
  secondary: {
    label: string;
    action: () => void;
    type: SecondaryActionType;
  };
}

export interface FixGuidanceCardProps {
  id: string;
  severity: FixGuidanceSeverity;
  issue: FixGuidanceIssue;
  impact: FixGuidanceImpact;
  remediation: FixGuidanceRemediation;
  correlationId?: string;
  timestamp: string;
  isDismissible: boolean;
  onDismiss?: () => void;
  /** Optional platform icon key for Integration 8 continuity */
  platformKey?: string;
}

export type FixGuidanceSortOrder = "severity_desc" | "timestamp_desc";

export type FixGuidanceFilter = "all" | "critical" | "actionable";

export interface FixGuidanceStackProps {
  cards: FixGuidanceCardProps[];
  maxVisible?: number;
  sortOrder?: FixGuidanceSortOrder;
  filter?: FixGuidanceFilter;
  onViewAll?: () => void;
}
