import React from 'react';
import { useNavigate } from 'react-router-dom';
import { BudgetScenario } from '../../types/budgetScenarios';
import { StatusBadge } from '../ui/StatusBadge';
import { Button } from '../ui/Button';

function timeAgo(isoDate: string): string {
  const ms = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(ms / 60000);
  const hours = Math.floor(mins / 60);
  const days = Math.floor(hours / 24);
  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (mins > 0) return `${mins}m ago`;
  return 'just now';
}

function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

function MoreIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="5" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="12" cy="19" r="1" />
    </svg>
  );
}

interface ScenarioCardProps {
  scenario: BudgetScenario;
  onAction?: (action: string, id: string) => void;
}

export function ScenarioCard({ scenario, onAction }: ScenarioCardProps) {
  const navigate = useNavigate();

  const goToDetail = () => navigate(`/budget/scenarios/${scenario.id}`);

  return (
    <div className="sc-card" onClick={goToDetail} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && goToDetail()}>
      <div className="sc-card__body">
        {/* Header row */}
        <div className="sc-card__header">
          <StatusBadge status={scenario.status} />
          <button
            className="sc-card__menu-btn"
            onClick={(e) => { e.stopPropagation(); }}
            aria-label="More actions"
          >
            <MoreIcon />
          </button>
        </div>

        {/* Title & meta */}
        <div className="sc-card__meta">
          <h3 className="sc-card__title">{scenario.name || `Scenario ${scenario.id.slice(-4).toUpperCase()}`}</h3>
          <p className="sc-card__sub">
            <span>{timeAgo(scenario.createdAt)}</span>
            <span className="sc-card__dot">·</span>
            <span>{scenario.dateRange.label}</span>
          </p>
        </div>

        {/* Status-based content */}
        <div className="sc-card__content">
          {scenario.status === 'processing' && scenario.progress && (
            <div className="sc-card__progress">
              <div className="sc-card__progress-row">
                <span>Processing</span>
                <span>{Math.round(scenario.progress.percentage)}%</span>
              </div>
              <div className="sc-card__progress-track">
                <div
                  className="sc-card__progress-fill"
                  style={{ width: `${scenario.progress.percentage}%` }}
                />
              </div>
              <p className="sc-card__progress-step">{scenario.progress.currentStep}</p>
              <p className="sc-card__progress-eta">{Math.ceil(scenario.progress.timeRemaining)}s remaining</p>
            </div>
          )}

          {scenario.status === 'completed' && scenario.summary && (
            <div className="sc-card__impact">
              <div className="sc-card__impact-row">
                <span className="sc-card__impact-label">Expected Revenue</span>
                <span className="sc-card__impact-value">
                  {formatCurrency(scenario.summary.expectedImpact.revenue)}
                  <span className="sc-card__impact-pct"> (+{scenario.summary.expectedImpact.revenuePercent}%)</span>
                </span>
              </div>
              <div className="sc-card__impact-row sc-card__impact-row--border">
                <span className="sc-card__impact-label">ROAS</span>
                <span className="sc-card__impact-value">
                  {scenario.summary.expectedImpact.roas.toFixed(2)}
                  <span className={scenario.summary.expectedImpact.roasDelta >= 0 ? 'sc-card__impact-pos' : 'sc-card__impact-neg'}>
                    {' '}({scenario.summary.expectedImpact.roasDelta >= 0 ? '+' : ''}{scenario.summary.expectedImpact.roasDelta.toFixed(2)})
                  </span>
                </span>
              </div>
            </div>
          )}

          {scenario.status === 'applied' && scenario.appliedStatus && (
            <div className="sc-card__applied">
              <p className="sc-card__applied-date">
                Applied {timeAgo(scenario.appliedStatus.appliedAt)}
              </p>
              <div className="sc-card__platforms">
                {scenario.appliedStatus.platformStatus.map((p, i) => (
                  <span
                    key={i}
                    className={`sc-card__platform-pill sc-card__platform-pill--${p.status}`}
                  >
                    {p.platform}
                  </span>
                ))}
              </div>
            </div>
          )}

          {(scenario.status === 'rejected' || scenario.status === 'failed') && (
            <p className="sc-card__rejected">
              {scenario.status === 'rejected' ? 'Recommendation was rejected' : 'Optimization failed'}
            </p>
          )}
        </div>
      </div>

      {/* Footer actions */}
      <div className="sc-card__footer">
        {scenario.status === 'completed' ? (
          <>
            <Button
              variant="primary"
              size="small"
              onClick={(e) => { e.stopPropagation(); navigate(`/budget/scenarios/${scenario.id}`); }}
            >
              Review
            </Button>
            <Button
              variant="secondary"
              size="small"
              onClick={(e) => { e.stopPropagation(); onAction?.('apply', scenario.id); navigate(`/budget/scenarios/${scenario.id}`); }}
            >
              Apply
            </Button>
          </>
        ) : scenario.status === 'processing' ? (
          <Button
            variant="secondary"
            size="small"
            onClick={(e) => { e.stopPropagation(); navigate(`/budget/scenarios/${scenario.id}`); }}
          >
            View Progress
          </Button>
        ) : (
          <Button
            variant="secondary"
            size="small"
            onClick={(e) => { e.stopPropagation(); navigate(`/budget/scenarios/${scenario.id}`); }}
          >
            View Details
          </Button>
        )}
      </div>
    </div>
  );
}
