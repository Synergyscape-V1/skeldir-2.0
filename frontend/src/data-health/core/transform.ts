import { computeHealthStatus, computeOverallScore } from "./healthStatus";
import type { DataHealthData, DataHealthResponse } from "./types";

export const transformDataHealthResponse = (response: DataHealthResponse): DataHealthData => {
  const trackingCoverage = response.tracking_coverage;
  const utmConsistency = response.utm_consistency;
  const revenueMatchRate = response.revenue_match_rate;
  const overallScore = computeOverallScore(trackingCoverage, utmConsistency, revenueMatchRate);
  const status = computeHealthStatus(overallScore);

  return {
    overallScore,
    status,
    lastUpdated: new Date(response.last_updated),
    trackingCoverage,
    utmConsistency,
    revenueMatchRate,
    issues: response.issues.map((issue) => ({
      id: issue.id,
      severity: issue.severity,
      title: issue.title,
      description: issue.description,
      detectedAt: new Date(issue.detected_at),
      affectedEntity: issue.affected_entity,
      fixGuide: issue.fix_guide
        ? {
            steps: issue.fix_guide.steps.map((step) => ({
              stepNumber: step.step_number,
              instruction: step.instruction,
              codeSnippet: step.code_snippet,
              resourceLink: step.resource_link
                ? {
                    text: step.resource_link.text,
                    url: step.resource_link.url,
                  }
                : undefined,
            })),
          }
        : undefined,
      resolvedAt: issue.resolved_at ? new Date(issue.resolved_at) : null,
    })),
  };
};
