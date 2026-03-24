import React from "react";
import { formatCurrency, formatROAS } from "../../../lib/formatters";
import type { BudgetRecommendation, ComparisonChannelData, WinnerDeclaration } from "../../../types/comparison";
import { confidenceTierDescription } from "../../core/logic";

interface DecisionHeroProps {
  winner: WinnerDeclaration | null;
  budgetRecommendation: BudgetRecommendation | null;
  channels: ComparisonChannelData[];
}

export function DecisionHero({ winner, budgetRecommendation, channels }: DecisionHeroProps) {
  const hasChannels = channels.length > 0;

  return (
    <section
      className={`cc-d-decision-hero ${winner ? "cc-d-has-winner" : "cc-d-no-winner"}`}
      role="status"
      aria-live="polite"
    >
      <div className="cc-d-decision-inner">
        {/* Winner section */}
        <div className="cc-d-winner-section">
          <span className="cc-d-decision-label">Recommended Action</span>
          {winner ? (
            <>
              <h3 className="cc-d-winner-name">{winner.channelName}</h3>
              <p className="cc-d-winner-detail">
                leads with <strong>{formatROAS(winner.roas)}</strong> ROAS
                {winner.delta > 0 ? ` (+${formatROAS(winner.delta)} vs runner-up)` : ""}
              </p>
              <p className="cc-d-winner-confidence">
                Confidence ranges confirmed non-overlapping.
              </p>
            </>
          ) : (
            <>
              <h3 className="cc-d-winner-name cc-d-muted">No reliable winner</h3>
              <p className="cc-d-winner-detail cc-d-muted">
                {hasChannels
                  ? "Confidence ranges overlap \u2014 gather more data before reallocating budget."
                  : "Add channels above to begin comparison."}
              </p>
            </>
          )}
        </div>

        {/* Budget recommendation section */}
        <div className="cc-d-budget-section">
          {budgetRecommendation ? (
            <>
              <span className="cc-d-budget-label">Budget Opportunity</span>
              <p className="cc-d-budget-text">
                Shift <strong>{formatCurrency(budgetRecommendation.shiftAmount)}</strong> from{" "}
                {budgetRecommendation.fromChannelName} to {budgetRecommendation.toChannelName}
              </p>
              <p className="cc-d-budget-lift">
                Expected lift: <strong>+{formatCurrency(budgetRecommendation.expectedRevenueIncrease)}</strong>
                {" "}({confidenceTierDescription(budgetRecommendation.confidence)})
              </p>
              <a href="/budget?source=comparison" className="cc-d-cta">
                Review in Budget Optimizer
              </a>
            </>
          ) : (
            <>
              <span className="cc-d-budget-label cc-d-muted">Budget Opportunity</span>
              <p className="cc-d-budget-text cc-d-muted">
                {winner
                  ? "No reallocation opportunity detected at current thresholds."
                  : "Declare a winner first to unlock budget recommendations."}
              </p>
              <a href="/budget?source=comparison" className="cc-d-cta cc-d-cta-muted">
                Review in Budget Optimizer
              </a>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
