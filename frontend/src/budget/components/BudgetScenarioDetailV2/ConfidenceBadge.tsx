import React from 'react';
import { CheckCircle, AlertCircle, AlertTriangle } from 'lucide-react';

const CONFIG: Record<string, {
  icon: typeof CheckCircle;
  label: string;
  score: string | null;
  className: string;
}> = {
  high: {
    icon: CheckCircle,
    label: 'High confidence',
    score: '≥ 70',
    className: 'bsdv2-confidence--high',
  },
  medium: {
    icon: AlertCircle,
    label: 'Moderate confidence',
    score: '< 70',
    className: 'bsdv2-confidence--medium',
  },
  low: {
    icon: AlertTriangle,
    label: 'Low confidence',
    score: null,
    className: 'bsdv2-confidence--low',
  },
};

interface Props {
  confidence: 'high' | 'medium' | 'low';
  showScore?: boolean;
  size?: 'sm' | 'md';
}

export function ConfidenceBadge({ confidence, showScore = true, size = 'md' }: Props) {
  const cfg = CONFIG[confidence];
  if (!cfg) return null;
  const Icon = cfg.icon;
  const iconSize = size === 'sm' ? 11 : 13;

  return (
    <span className={`bsdv2-confidence ${cfg.className}`}>
      <Icon size={iconSize} />
      {cfg.label}
      {showScore && cfg.score && (
        <span className="bsdv2-confidence-score">Score {cfg.score}</span>
      )}
    </span>
  );
}
