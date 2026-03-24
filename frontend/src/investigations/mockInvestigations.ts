export type InvestigationStatus = "pending" | "processing" | "completed" | "failed";
export type InvestigationPriority = "user" | "auto";

export interface Investigation {
  id: string;
  question: string;
  status: InvestigationStatus;
  priority: InvestigationPriority;
  cost: number;
  createdAt: Date;
  failureReason?: string;
  piiRemoved?: boolean;
}

export interface InvestigationDetail extends Investigation {
  summary?: string;
  findings?: { title: string; detail: string; confidence: string; confidencePercent: string }[];
  overallConfidence?: string;
  dataPeriod?: string;
  timeline?: { timestamp: string; label: string; detail: string; status: "completed" | "pending" }[];
  sqlQueries?: { title: string; sql: string; rows: number; executionTime: string }[];
  reviewStatus?: "pending" | "approved" | "rejected";
}

const now = new Date();
const ago = (minutes: number) => new Date(now.getTime() - minutes * 60000);

export const mockInvestigations: Investigation[] = [
  {
    id: "inv_a7f3c2",
    question: "Why did Facebook ROAS drop 40% in Q4 despite increased spend?",
    status: "pending",
    priority: "user",
    cost: 0.4,
    createdAt: ago(2),
  },
  {
    id: "inv_b2d4e1",
    question: "Weekly performance anomaly check",
    status: "pending",
    priority: "auto",
    cost: 0.2,
    createdAt: ago(60),
  },
  {
    id: "inv_c9a1b3",
    question: "Compare Q3 vs Q4 channel mix",
    status: "completed",
    priority: "user",
    cost: 0.35,
    createdAt: ago(180),
  },
  {
    id: "inv_d4e2f5",
    question: "Explain the confidence level for the current ROAS estimate",
    status: "failed",
    priority: "auto",
    cost: 0.0,
    createdAt: ago(300),
    failureReason: "Insufficient data for comparison period",
    piiRemoved: true,
  },
  {
    id: "inv_e5f3a1",
    question: "Analyze customer churn rate for last month",
    status: "completed",
    priority: "auto",
    cost: 0.2,
    createdAt: ago(120),
  },
  {
    id: "inv_f6a4b2",
    question: "Identify top performing ad creatives",
    status: "completed",
    priority: "auto",
    cost: 0.2,
    createdAt: ago(120),
  },
  {
    id: "inv_g7b5c3",
    question: "Why did average order value decrease?",
    status: "pending",
    priority: "user",
    cost: 0.35,
    createdAt: ago(180),
  },
  {
    id: "inv_h8c6d4",
    question: "Why did average order value decrease?",
    status: "pending",
    priority: "user",
    cost: 0.4,
    createdAt: ago(180),
  },
  {
    id: "inv_i9d7e5",
    question: "Why did average order value decrease?",
    status: "pending",
    priority: "user",
    cost: 0.35,
    createdAt: ago(180),
  },
  {
    id: "inv_j1e8f6",
    question: "Analyze customer churn rate for last month",
    status: "completed",
    priority: "auto",
    cost: 0.2,
    createdAt: ago(120),
  },
  {
    id: "inv_k2f9a7",
    question: "Di conversion volume drop because spend changed or efficiency",
    status: "failed",
    priority: "user",
    cost: 0.35,
    createdAt: ago(180),
  },
  {
    id: "inv_l3a1b8",
    question: "Why did average order value decrease?",
    status: "completed",
    priority: "auto",
    cost: 0.0,
    createdAt: ago(120),
  },
];

export const mockDetailData: InvestigationDetail = {
  id: "inv_a7f3c2",
  question: "Why did Facebook ROAS drop 40% in Q4 despite increased spend?",
  status: "completed",
  priority: "user",
  cost: 0.4,
  createdAt: ago(360),
  summary:
    "Facebook's ROAS declined from $4.20 to $2.52 (40% drop) due to three primary factors identified through Bayesian analysis:",
  findings: [
    {
      title: "Creative fatigue",
      detail: "Top 3 ad sets show 60% frequency increase",
      confidence: "High",
      confidencePercent: "\u00b18%",
    },
    {
      title: "Auction competition",
      detail: "CPM increased 35% vs Q3",
      confidence: "Medium",
      confidencePercent: "\u00b115%",
    },
    {
      title: "Attribution gap",
      detail: "23% of claimed revenue unverified",
      confidence: "High",
      confidencePercent: "\u00b15%",
    },
  ],
  overallConfidence: "Medium (\u00b118%)",
  dataPeriod: "Oct 1 \u2013 Dec 1, 2024",
  timeline: [
    { timestamp: "11:23:14 PM", label: "Received question", detail: "Question parsed and validated", status: "completed" },
    { timestamp: "11:23:45 PM", label: "Analyzed data sources", detail: "Queried 3 tables (247 rows)", status: "completed" },
    { timestamp: "11:24:02 PM", label: "Identified anomalies", detail: "Found 12% variance in Facebook revenue attribution", status: "completed" },
    { timestamp: "11:24:30 PM", label: "Synthesized findings", detail: "Generated 3 primary insights", status: "completed" },
    { timestamp: "11:24:58 PM", label: "Complete", detail: "Investigation finalized", status: "completed" },
  ],
  sqlQueries: [
    {
      title: "Revenue attribution by channel",
      sql: `SELECT channel, SUM(attributed_revenue) / SUM(spend) as roas\nFROM attribution_results\nWHERE date >= '2024-10-01' AND date <= '2024-12-01'\nGROUP BY channel`,
      rows: 4,
      executionTime: "45ms",
    },
    {
      title: "Ad set frequency analysis",
      sql: `SELECT ad_set_name, AVG(frequency) as avg_freq,\n  SUM(spend) as total_spend, SUM(revenue) / SUM(spend) as roas\nFROM ad_performance\nWHERE channel = 'facebook' AND quarter = 'Q4'\nGROUP BY ad_set_name\nORDER BY avg_freq DESC\nLIMIT 10`,
      rows: 10,
      executionTime: "120ms",
    },
    {
      title: "CPM trend comparison",
      sql: `SELECT DATE_TRUNC('week', date) as week,\n  AVG(cpm) as avg_cpm, quarter\nFROM ad_metrics\nWHERE channel = 'facebook'\n  AND date >= '2024-07-01'\nGROUP BY week, quarter\nORDER BY week`,
      rows: 24,
      executionTime: "89ms",
    },
  ],
  reviewStatus: "pending",
};

export function formatRelativeTime(date: Date): string {
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export function formatCurrency(cents: number): string {
  return `$${cents.toFixed(2)}`;
}
