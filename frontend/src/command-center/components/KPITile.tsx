import React from 'react';
import { VerificationBadge } from './Badges';
import CredibleIntervalBar from './CredibleIntervalBar';

export type TrendDirection = 'up' | 'down' | 'neutral';
export type TrendSentiment = 'positive' | 'negative' | 'neutral';

export interface KPITileTrend {
  direction: TrendDirection;
  value: string;
  sentiment: TrendSentiment;
  comparisonHint?: string;
}

export interface KPITileConfidenceRange {
  lower: number;
  upper: number;
  estimate: number;
  lowerLabel: string;
  upperLabel: string;
  bucket: 'narrow' | 'medium' | 'wide';
  actionImplication?: string;
}

export interface KPITileProps {
  label: string;
  value: string;
  trend?: KPITileTrend;
  context?: string;
  confidenceRange?: KPITileConfidenceRange;
  verifiedStatus?: 'verified' | 'unverified' | 'partial';
  infoTooltip?: string;
  isLoading?: boolean;
  onTileClick?: () => void;
}

export default function KPITile({
  label,
  value,
  trend,
  context,
  confidenceRange,
  verifiedStatus,
  infoTooltip,
  isLoading,
  onTileClick,
}: KPITileProps) {
  const trendClass =
    trend == null
      ? ''
      : trend.sentiment === 'positive'
        ? 'cc-kpi-tile__trend--positive'
        : trend.sentiment === 'negative'
          ? 'cc-kpi-tile__trend--negative'
          : 'cc-kpi-tile__trend--neutral';

  const trendTitle = trend?.comparisonHint ?? 'Compared to prior 30 days';

  const ciTitle =
    confidenceRange &&
    `${confidenceRange.lowerLabel} – ${confidenceRange.upperLabel}${
      confidenceRange.actionImplication ? `. ${confidenceRange.actionImplication}` : ''
    }`;

  return (
    <article
      className={`cc-kpi-tile${onTileClick ? ' cc-kpi-tile--interactive' : ''}${
        verifiedStatus === 'verified' ? ' cc-kpi-tile--has-verified-badge' : ''
      }`}
      title={infoTooltip}
      onClick={onTileClick}
      onKeyDown={
        onTileClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onTileClick();
              }
            }
          : undefined
      }
      role={onTileClick ? 'button' : undefined}
      tabIndex={onTileClick ? 0 : undefined}
    >
      {verifiedStatus === 'verified' && (
        <div className="cc-kpi-tile__badge-corner">
          <VerificationBadge status="verified" source="Verified" />
        </div>
      )}
      <p className="cc-kpi-tile__label">{label}</p>

      <div className="cc-kpi-tile__value-row">
        <p className="cc-kpi-tile__value" aria-live="polite">
          {isLoading ? '—' : value}
        </p>
      </div>

      {trend && (
        <span className={`cc-kpi-tile__trend ${trendClass}`} title={trendTitle}>
          {trend.value}
        </span>
      )}

      {context && <p className="cc-kpi-tile__context">{context}</p>}

      {confidenceRange && (
        <div className="cc-kpi-tile__ci" title={ciTitle}>
          <div className="cc-kpi-tile__ci-inner">
            <div className="cc-kpi-tile__ci-labels">
              <span>{confidenceRange.lowerLabel}</span>
              <span>{confidenceRange.upperLabel}</span>
            </div>
            <div className="cc-kpi-tile__ci-bar-wrap">
              <CredibleIntervalBar
                lower={confidenceRange.lower}
                upper={confidenceRange.upper}
                estimate={confidenceRange.estimate}
                bucket={confidenceRange.bucket}
                height={4}
                widthPercent={100}
              />
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
