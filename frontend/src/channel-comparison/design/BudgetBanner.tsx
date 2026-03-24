import type { BudgetRecommendation } from "../../types/comparison";
import { formatCurrency } from "../../lib/formatters";

interface BudgetBannerProps {
  recommendation: BudgetRecommendation;
}

function confidenceLabel(level: string): string {
  if (level === "high") return "High";
  if (level === "medium") return "Medium";
  return "Low";
}

export function BudgetBanner({ recommendation }: BudgetBannerProps) {
  return (
    <div className="dc-budget-banner">
      <div className="dc-budget-banner-text">
        <p>Recommended budget shift</p>
        <p>
          Shift {formatCurrency(recommendation.shiftAmount)} from {recommendation.fromChannelName} to{" "}
          {recommendation.toChannelName}. ({confidenceLabel(recommendation.confidence)} Confidence,
          estimated +{formatCurrency(recommendation.expectedRevenueIncrease)} revenue impact).
        </p>
      </div>
      <div className="dc-budget-banner-actions">
        <button type="button" className="dc-btn-outline">
          Review in Budget Optimizer
        </button>
        <button type="button" className="dc-btn-outline">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Export Comparison
        </button>
      </div>
    </div>
  );
}
