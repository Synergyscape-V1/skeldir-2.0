import { transformDataHealthResponse } from "./transform";
import type { DataHealthData, DataHealthResponse, DataHealthScenario } from "./types";

const ISSUE_FIX_GUIDE = {
  steps: [
    {
      step_number: 1,
      instruction: "Copy the Skeldir tracking snippet from settings.",
      resource_link: { text: "View tracking snippet", url: "/settings/tracking" },
    },
    {
      step_number: 2,
      instruction: "Paste the snippet in the page head and publish.",
      code_snippet: "<script src=\"https://cdn.skeldir.com/v1/skeldir.js\"></script>",
    },
  ],
};

const BASE_WARNING: DataHealthResponse = {
  tracking_coverage: 87,
  utm_consistency: 82,
  revenue_match_rate: 76,
  issues: [
    {
      id: "issue_tracking_gap_homepage",
      severity: "critical",
      title: "Homepage missing tracking tag",
      description: "Homepage traffic is not sending tracking events, causing attribution blind spots.",
      detected_at: "2026-02-18T14:30:00Z",
      affected_entity: "Homepage (www.example.com)",
      fix_guide: ISSUE_FIX_GUIDE,
      resolved_at: null,
    },
    {
      id: "issue_utm_inconsistent",
      severity: "warning",
      title: "Campaign UTM inconsistency",
      description: "Some campaigns use non-standard source and campaign parameters.",
      detected_at: "2026-02-19T11:15:00Z",
      affected_entity: "Meta Ads (12 campaigns)",
      fix_guide: null,
      resolved_at: null,
    },
    {
      id: "issue_info_audit",
      severity: "info",
      title: "Quarterly webhook audit recommended",
      description: "Run a quarterly webhook payload audit to maintain schema hygiene.",
      detected_at: "2026-02-19T09:00:00Z",
      affected_entity: "All connected platforms",
      fix_guide: { steps: [] },
      resolved_at: null,
    },
  ],
  last_updated: "2026-02-19T12:45:00Z",
};

const SCENARIO_RESPONSES: Record<DataHealthScenario, DataHealthResponse> = {
  good: {
    tracking_coverage: 97,
    utm_consistency: 95,
    revenue_match_rate: 93,
    issues: [
      {
        id: "issue_info_cleanup",
        severity: "info",
        title: "Minor naming cleanup available",
        description: "A small set of campaign names can be normalized for clearer reporting.",
        detected_at: "2026-02-19T08:00:00Z",
        affected_entity: "Google Ads (2 campaigns)",
        fix_guide: null,
        resolved_at: null,
      },
    ],
    last_updated: "2026-02-20T11:00:00Z",
  },
  warning: BASE_WARNING,
  critical: {
    tracking_coverage: 62,
    utm_consistency: 68,
    revenue_match_rate: 57,
    issues: [
      ...BASE_WARNING.issues,
      {
        id: "issue_revenue_mismatch",
        severity: "critical",
        title: "Revenue webhook mismatch above threshold",
        description: "Mismatch between platform webhooks and tracked revenue exceeds 20%.",
        detected_at: "2026-02-20T10:10:00Z",
        affected_entity: "TikTok Ads",
        fix_guide: {
          steps: [
            {
              step_number: 1,
              instruction: "Regenerate webhook secret in the platform integration panel.",
              resource_link: { text: "Go to integrations", url: "/data/integrations" },
            },
          ],
        },
        resolved_at: null,
      },
    ],
    last_updated: "2026-02-20T07:30:00Z",
  },
};

export interface FetchDataHealthOptions {
  scenario: DataHealthScenario;
  stale?: boolean;
  delayMs?: number;
  shouldFail?: boolean;
  noData?: boolean;
}

export async function fetchDataHealthMock(options: FetchDataHealthOptions): Promise<DataHealthData | null> {
  const { scenario, stale = false, delayMs = 350, shouldFail = false, noData = false } = options;
  await new Promise((resolve) => setTimeout(resolve, delayMs));

  if (shouldFail) {
    throw new Error("Unable to load data health metrics. Please try again.");
  }

  if (noData) return null;

  const response = SCENARIO_RESPONSES[scenario];
  const withStaleTimestamp: DataHealthResponse = {
    ...response,
    last_updated: stale ? "2026-02-15T09:00:00Z" : response.last_updated,
  };

  return transformDataHealthResponse(withStaleTimestamp);
}
