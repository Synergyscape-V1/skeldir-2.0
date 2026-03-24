import React from 'react';
import { ScenarioSummary } from '../../types/budgetScenarios';

function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

interface RecommendationSummaryCardProps {
  summary: ScenarioSummary;
}

export function RecommendationSummaryCard({ summary }: RecommendationSummaryCardProps) {
  return (
    <div className="rsc-card">
      {/* Description column */}
      <div className="rsc-desc-col">
        <h3 className="rsc-title">Recommendation Summary</h3>
        <p className="rsc-desc">{summary.description}</p>
      </div>

      {/* Impact metrics column */}
      <div className="rsc-impact-col">
        <div className="rsc-metric">
          <p className="rsc-metric-label">Expected Revenue</p>
          <div className="rsc-metric-value-row">
            <span className="rsc-metric-value">{formatCurrency(summary.expectedImpact.revenue)}</span>
            <span className="rsc-pill rsc-pill--green">+{summary.expectedImpact.revenuePercent}%</span>
          </div>
        </div>

        <div className="rsc-metric">
          <p className="rsc-metric-label">Projected ROAS</p>
          <div className="rsc-metric-value-row">
            <span className="rsc-metric-value">{summary.expectedImpact.roas.toFixed(2)}</span>
            <span className={`rsc-pill ${summary.expectedImpact.roasDelta >= 0 ? 'rsc-pill--green' : 'rsc-pill--red'}`}>
              {summary.expectedImpact.roasDelta >= 0 ? '+' : ''}{summary.expectedImpact.roasDelta.toFixed(2)}
            </span>
          </div>
        </div>

        <div className="rsc-confidence">
          <span className="rsc-confidence-label">Confidence Level</span>
          <span className={`rsc-confidence-badge rsc-confidence-badge--${summary.confidence}`}>
            {summary.confidence.charAt(0).toUpperCase() + summary.confidence.slice(1)} Confidence
          </span>
        </div>
      </div>
    </div>
  );
}
