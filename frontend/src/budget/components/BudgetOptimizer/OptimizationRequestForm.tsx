import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { mockApi } from '../../services/mockApi';
import { Button } from '../ui/Button';
import { DateRangeValue, OptimizationGoal, OptimizationConstraints } from '../../types/budgetScenarios';

function CalendarIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function BarChartIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

const GOAL_OPTIONS: Array<{ value: OptimizationGoal; label: string; description: string; recommended?: boolean }> = [
  { value: 'maximize_revenue', label: 'Maximize Revenue', description: 'Prioritize top-line growth', recommended: true },
  { value: 'maximize_roas', label: 'Maximize ROAS', description: 'Prioritize efficiency' },
  { value: 'minimize_cac', label: 'Minimize CAC', description: 'Prioritize acquisition cost' },
];

export function OptimizationRequestForm() {
  const navigate = useNavigate();
  const [dateRange, setDateRange] = useState<DateRangeValue>('last_30_days');
  const [goal, setGoal] = useState<OptimizationGoal>('maximize_revenue');
  const [constraints, setConstraints] = useState<OptimizationConstraints>({
    keepTotalSpendWithinPercent: 10,
    maxChannelReductionPercent: 20,
    minimumChannelSpend: 50000,
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const scenario = await mockApi.createScenario({ dateRange, goal, constraints });
      navigate(`/budget/scenarios/${scenario.id}`);
    } catch {
      alert('Failed to create optimization request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="orf-form">
      {/* Date Range */}
      <div className="orf-field">
        <label className="orf-label">Date Range</label>
        <div className="orf-select-wrap">
          <span className="orf-select-icon"><CalendarIcon /></span>
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value as DateRangeValue)}
            className="orf-select"
          >
            <option value="last_30_days">Last 30 Days</option>
            <option value="last_60_days">Last 60 Days</option>
            <option value="last_90_days">Last 90 Days</option>
            <option value="custom">Custom Range</option>
          </select>
        </div>
      </div>

      {/* Model */}
      <div className="orf-field">
        <label className="orf-label">Model</label>
        <div className="orf-select-wrap orf-select-wrap--disabled">
          <span className="orf-select-icon"><BarChartIcon /></span>
          <select disabled className="orf-select orf-select--disabled">
            <option>Bayesian MMM (Recommended)</option>
          </select>
        </div>
        <p className="orf-hint">Only Bayesian MMM is available for this account tier.</p>
      </div>

      {/* Optimization Goal */}
      <div className="orf-field">
        <label className="orf-label">Optimization Goal</label>
        <div className="orf-goal-group">
          {GOAL_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`orf-goal-item${goal === opt.value ? ' orf-goal-item--selected' : ''}`}
            >
              <input
                type="radio"
                name="goal"
                value={opt.value}
                checked={goal === opt.value}
                onChange={() => setGoal(opt.value)}
                className="orf-radio"
              />
              <div className="orf-goal-text">
                <span className="orf-goal-label">
                  {opt.label}
                  {opt.recommended && (
                    <span className="orf-recommended-pill">Recommended</span>
                  )}
                </span>
                <span className="orf-goal-desc">{opt.description}</span>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Constraints */}
      <div className="orf-field">
        <label className="orf-label">Constraints</label>
        <div className="orf-checkbox-group">
          <label className="orf-checkbox-item">
            <input
              type="checkbox"
              checked={!!constraints.keepTotalSpendWithinPercent}
              onChange={(e) =>
                setConstraints((prev) => ({
                  ...prev,
                  keepTotalSpendWithinPercent: e.target.checked ? 10 : undefined,
                }))
              }
              className="orf-checkbox"
            />
            <span className="orf-checkbox-label">Keep total spend within ±10%</span>
          </label>
          <label className="orf-checkbox-item">
            <input
              type="checkbox"
              checked={!!constraints.maxChannelReductionPercent}
              onChange={(e) =>
                setConstraints((prev) => ({
                  ...prev,
                  maxChannelReductionPercent: e.target.checked ? 20 : undefined,
                }))
              }
              className="orf-checkbox"
            />
            <span className="orf-checkbox-label">Never reduce any channel by more than 20%</span>
          </label>
          <label className="orf-checkbox-item">
            <input
              type="checkbox"
              checked={!!constraints.minimumChannelSpend}
              onChange={(e) =>
                setConstraints((prev) => ({
                  ...prev,
                  minimumChannelSpend: e.target.checked ? 50000 : undefined,
                }))
              }
              className="orf-checkbox"
            />
            <span className="orf-checkbox-label">Maintain minimum $500/channel (prevent shutdown)</span>
          </label>
        </div>
      </div>

      {/* Submit */}
      <div className="orf-submit-wrap">
        <Button type="submit" variant="primary" size="lg" fullWidth isLoading={loading} disabled={loading}>
          {loading ? 'Analyzing…' : 'Generate Recommendation'}
        </Button>
        <p className="orf-submit-hint">This takes 45–60 seconds. You'll be notified when ready.</p>
      </div>
    </form>
  );
}
