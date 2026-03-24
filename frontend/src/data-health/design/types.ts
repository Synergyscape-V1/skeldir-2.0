/* DataHealthIssue — richer type used by the design-system components
   (MetricCard, PriorityIssuesSection, FixGuide, DataHealthDashboard).
   Adapter from DataIssue → DataHealthIssue lives in DataHealthDashboard. */

export interface DataHealthIssue {
  id: string;
  severity: "critical" | "warning" | "info";
  title: string;
  description: string;
  /** Short impact descriptor shown beneath the description in the issues list */
  impact?: string;
  /** One-sentence problem statement for the Fix Guide */
  problem: string;
  /** Why this happened — shown in the Fix Guide */
  why: string;
  /** Ordered fix steps */
  whatToDo: Array<{
    stepId: string;
    text: string;
    primaryAction?: { label: string };
  }>;
  /** Deadline label e.g. "ASAP" or "This week" */
  fixBy?: string;
  /** Correlation/error ID shown in the Fix Guide footer */
  correlationId?: string;
}
