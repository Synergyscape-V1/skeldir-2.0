import React from "react";
import { formatCurrency, formatROAS } from "../../lib/formatters";
import type { BudgetRecommendation, ComparisonChannelData, ComparisonPanelError, WinnerDeclaration } from "../../types/comparison";
import { budgetRecommendationText, confidenceTierDescription } from "../core/logic";

export function GlobalErrorBanner({
  error,
  onRetry,
}: {
  error: ComparisonPanelError;
  onRetry: () => void;
}) {
  return (
    <section className="cc-global-error" role="alert">
      <div>
        <p>Could not load channel list. Type channel IDs manually.</p>
        <small>Error ID: {error.correlationId ?? "unavailable"}</small>
      </div>
      <button type="button" onClick={onRetry}>
        Retry
      </button>
    </section>
  );
}

export function WinnerBanner({
  winner,
  channels,
}: {
  winner: WinnerDeclaration | null;
  channels: ComparisonChannelData[];
}) {
  if (!winner) return null;
  const runnerUp = [...channels]
    .sort((a, b) => b.performance.roas - a.performance.roas)
    .find((channel) => channel.channel.id !== winner.channelId);
  return (
    <section className="cc-winner-banner" role="status" aria-live="polite">
      <p>
        {winner.channelName} leads with the highest ROAS ({formatROAS(winner.roas)}
        {runnerUp ? ` vs ${runnerUp.channel.name} ${formatROAS(runnerUp.performance.roas)}` : ""})
      </p>
      <small>Confidence ranges confirmed non-overlapping.</small>
    </section>
  );
}

export function BudgetRecommendationBanner({
  recommendation,
}: {
  recommendation: BudgetRecommendation | null;
}) {
  if (!recommendation) return null;
  return (
    <section className="cc-recommendation-banner">
      <div className="cc-recommendation-content">
        <h3>Recommended budget shift</h3>
        <p>
          {budgetRecommendationText(recommendation)}. ({confidenceTierDescription(recommendation.confidence)}, estimated +{formatCurrency(recommendation.expectedRevenueIncrease)} revenue impact).
        </p>
      </div>
      <div className="cc-recommendation-actions">
        <a href="/budget?source=comparison" className="cc-recommendation-cta">Review in Budget Optimizer</a>
        <button type="button" className="cc-recommendation-export">↓ Export Comparison</button>
      </div>
    </section>
  );
}

export function ModelRecommendationPanel({
  recommendation,
  winnerName,
}: {
  recommendation: BudgetRecommendation | null;
  winnerName?: string;
}) {
  if (!recommendation) return null;
  return (
    <aside className="cc-model-panel">
      <h3>Why this model recommendation</h3>
      <p>
        Our model identifies {winnerName ?? recommendation.toChannelName} as the most reliably profitable channel. Shifting budget from the higher volatility {recommendation.fromChannelName} maximizes probability of better returns.
      </p>
      <p className="cc-model-panel-disclaimer">
        <em>Final budget allocation requires your approval.</em>
      </p>
      <a href="/budget?source=comparison" className="cc-model-panel-cta">Open in Budget Optimizer</a>
    </aside>
  );
}

export function EmptyComparisonState() {
  return (
    <section className="cc-empty-state">
      <p className="cc-empty-icon" aria-hidden>
        [chart]
      </p>
      <h2>Select channels to compare</h2>
      <p>Choose 2 or more channels from the menu above to see a side-by-side performance comparison with confidence ranges.</p>
    </section>
  );
}
