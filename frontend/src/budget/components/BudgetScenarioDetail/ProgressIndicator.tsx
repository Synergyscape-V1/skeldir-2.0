import React from 'react';
import { ScenarioProgress } from '../../types/budgetScenarios';
import { Button } from '../ui/Button';

function CheckCircleIcon() {
  return (
    <img
      src="/checkmark-svgrepo-com.svg"
      width={18}
      height={18}
      aria-hidden="true"
      alt="Step complete"
    />
  );
}

function LoaderIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="bsd-spin" aria-hidden>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}

function CircleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

interface ProgressIndicatorProps {
  progress: ScenarioProgress;
  onCancel: () => void;
}

export function ProgressIndicator({ progress, onCancel }: ProgressIndicatorProps) {
  return (
    <div className="pi-card" role="region" aria-label="Budget optimization progress">
      <div className="pi-header">
        <div>
          <h3 className="pi-title">Generating Budget Recommendation</h3>
          <p className="pi-desc">Running optimization model. This usually takes 45–60 seconds.</p>
        </div>
        <div className="pi-pct-block" aria-live="polite">
          <span className="pi-pct">{Math.round(progress.percentage)}%</span>
          <span className="pi-eta">{Math.ceil(progress.timeRemaining)}s remaining</span>
        </div>
      </div>

      <div className="pi-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress.percentage)} aria-label="Optimization completion">
        <div className="pi-fill" style={{ width: `${progress.percentage}%` }} />
      </div>

      <section className="pi-steps" aria-label="Optimization steps">
        {progress.steps.map((step, i) => (
          <div
            key={i}
            className={`pi-step pi-step--${step.status}`}
            aria-current={step.status === 'current' ? 'step' : undefined}
          >
            <span className="pi-step-icon" aria-hidden="true">
              {step.status === 'complete' ? <CheckCircleIcon /> : step.status === 'current' ? <LoaderIcon /> : <CircleIcon />}
            </span>
            <span className="pi-step-label">{step.label}</span>
          </div>
        ))}
      </section>

      <div className="pi-footer">
        <Button variant="tertiary" onClick={onCancel}>Cancel Generation</Button>
      </div>
    </div>
  );
}
