import React from 'react';
import { ScenarioStatus } from '../../types/budgetScenarios';
import '../../budget-shared.css';

const LABELS: Record<ScenarioStatus, string> = {
  draft: 'Draft',
  processing: 'Processing',
  completed: 'Completed',
  applied: 'Applied',
  rejected: 'Rejected',
  failed: 'Failed',
};

interface StatusBadgeProps {
  status: ScenarioStatus;
  className?: string;
}

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  return (
    <span className={`bud-status-badge bud-status-badge--${status} ${className}`}>
      <span className="bud-status-badge--dot" />
      {LABELS[status]}
    </span>
  );
}
