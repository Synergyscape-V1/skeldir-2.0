import type { MatchCategory } from "./revenueMatchingTypes";

/** Constitutional thresholds — variance from API (`/api/v1/revenue/verification`). */
export function getCategoryFromDiscrepancyPct(absPct: number, hasVerifiedData: boolean): MatchCategory {
  if (!hasVerifiedData || Number.isNaN(absPct)) return "unmatched";
  if (absPct <= 2) return "matched";
  if (absPct <= 10) return "flagged";
  return "severe";
}
