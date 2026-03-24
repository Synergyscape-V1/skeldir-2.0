import React from "react";
import { formatCurrency } from "../../../lib/formatters";
import type { BudgetRecommendation } from "../../../types/comparison";
import { budgetRecommendationText, confidenceTierDescription } from "../../core/logic";

interface ConfidenceAwareBudgetBannerProps {
  recommendation: BudgetRecommendation | null;
}

export function ConfidenceAwareBudgetBanner({ recommendation }: ConfidenceAwareBudgetBannerProps) {
  if (!recommendation) return null;

  return (
    <section className="cc-c-budget-banner">
      <div>
        <span className="cc-c-budget-prefix">Based on confidence analysis:</span>
        <h3>Budget Opportunity</h3>
        <p>{budgetRecommendationText(recommendation)}</p>
        <small>
          Expected lift: +{formatCurrency(recommendation.expectedRevenueIncrease)} (
          {confidenceTierDescription(recommendation.confidence)}).
        </small>
      </div>
      <a href="/budget?source=comparison">Review in Budget Optimizer</a>
    </section>
  );
}
