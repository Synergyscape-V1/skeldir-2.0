/**
 * Final Single Channel Detail — Performance Metrics
 *
 * Visual treatment: DA-2 DOSSIER (evidence citations, typography, microcopy).
 * Layout: DA-1 COCKPIT horizontal 4-tile row.
 * Theme: Light enterprise.
 *
 * All values pre-formatted — no client-side calculations.
 */

import React from 'react';
import type { ChannelDetailData } from '@/explorations/channel-detail/shared/types';
import { tokens } from '../tokens';

function deltaColor(delta: string): string {
  if (delta.startsWith('+')) return tokens.positive;
  if (delta.startsWith('-')) {
    // For CPA, a negative delta is good (cost went down)
    if (delta.includes('$')) return tokens.positive;
    return tokens.negative;
  }
  return tokens.neutral;
}

interface MetricDef {
  label: string;
  valueKey: keyof ChannelDetailData['performance'];
  deltaKey: keyof ChannelDetailData['performance'];
  citation: (p: ChannelDetailData['performance'], v: ChannelDetailData['verification']) => string;
}

const METRICS: MetricDef[] = [
  {
    label: 'Verified Revenue',
    valueKey: 'revenueFormatted',
    deltaKey: 'revenueDelta',
    citation: (_p, v) => `Source: ${v.transactionCountFormatted} via ${v.revenueSource}`,
  },
  {
    label: 'Ad Spend',
    valueKey: 'spendFormatted',
    deltaKey: 'spendDelta',
    citation: (p) => `Source: Platform-reported spend across ${p.conversionsFormatted} conversions`,
  },
  {
    label: 'ROAS',
    valueKey: 'roasFormatted',
    deltaKey: 'roasDelta',
    citation: (_p, v) => `Source: Verified revenue / reported spend, cross-referenced via ${v.revenueSource}`,
  },
  {
    label: 'Conversions',
    valueKey: 'conversionsFormatted',
    deltaKey: 'conversionsDelta',
    citation: (_p, v) => `Source: ${v.transactionCountFormatted} matched in ${v.revenueSource}`,
  },
];

interface PerformanceMetricsProps {
  performance: ChannelDetailData['performance'];
  verification: ChannelDetailData['verification'];
}

export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({
  performance,
  verification,
}) => (
  <>
    <style>{`
      @media (max-width: 768px) {
        .final-kpi-grid { grid-template-columns: 1fr 1fr !important; }
      }
      @media (max-width: 480px) {
        .final-kpi-grid { grid-template-columns: 1fr !important; }
      }
    `}</style>
    <div
      className="final-kpi-grid"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '16px',
      }}
    >
      {METRICS.map((metric) => {
        const value = performance[metric.valueKey] as string;
        const delta = performance[metric.deltaKey] as string;
        const cite = metric.citation(performance, verification);

        return (
          <div
            key={metric.label}
            style={{
              background: tokens.bg.card,
              border: `1px solid ${tokens.border.default}`,
              borderRadius: tokens.radius.md,
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              boxShadow: tokens.shadow.sm,
            }}
          >
            <p
              style={{
                fontFamily: tokens.font.body,
                fontSize: '12px',
                fontWeight: 500,
                color: tokens.text.muted,
                letterSpacing: '0.5px',
                textTransform: 'uppercase',
                margin: 0,
              }}
            >
              {metric.label}
            </p>
            <p
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '32px',
                fontWeight: 600,
                color: tokens.text.primary,
                lineHeight: 1.1,
                margin: 0,
              }}
            >
              {value}
            </p>
            <p
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '13px',
                fontWeight: 500,
                color: deltaColor(delta),
                margin: 0,
              }}
            >
              {delta}
            </p>
            <p
              style={{
                fontFamily: tokens.font.body,
                fontSize: '11px',
                color: tokens.text.muted,
                fontStyle: 'italic',
                marginTop: '4px',
                lineHeight: 1.4,
              }}
            >
              {cite}
            </p>
          </div>
        );
      })}
    </div>
  </>
);

export default PerformanceMetrics;
