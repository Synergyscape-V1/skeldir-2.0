/**
 * DA-3 TIMELINE — Verification Section
 *
 * Revenue verification panel showing platform-claimed vs verified revenue.
 * Two proportional bars with discrepancy percentage and severity coloring:
 *   - Green  (<5%)  = minor discrepancy
 *   - Amber  (5-15%) = moderate discrepancy
 *   - Red    (>15%) = significant discrepancy
 *
 * Revenue source citation and transaction count below.
 * All values arrive pre-formatted. No client-side calculations.
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';

/* -- Design Tokens -------------------------------------------------------- */
const tokens = {
  bg: {
    card: '#111827',
    nested: '#1F2937',
    elevated: '#263244',
  },
  text: {
    primary: '#F0F4FF',
    secondary: '#8B9AB8',
    muted: '#4A5568',
  },
  severity: {
    low: '#10D98C',     // <5% discrepancy
    medium: '#F5A623',  // 5-15% discrepancy
    high: '#F04E4E',    // >15% discrepancy
  },
  border: {
    subtle: 'rgba(139,154,184,0.12)',
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  motion: {
    short: '200ms',
    medium: '300ms',
  },
} as const;

/** Determine severity color from absolute discrepancy percentage */
function severityColor(discrepancyPercent: number): string {
  const abs = Math.abs(discrepancyPercent);
  if (abs < 5) return tokens.severity.low;
  if (abs <= 15) return tokens.severity.medium;
  return tokens.severity.high;
}

function severityLabel(discrepancyPercent: number): string {
  const abs = Math.abs(discrepancyPercent);
  if (abs < 5) return 'Minor discrepancy';
  if (abs <= 15) return 'Moderate discrepancy';
  return 'Significant discrepancy';
}

/* -- Component ------------------------------------------------------------ */

interface VerificationSectionProps {
  verification: ChannelDetailData['verification'];
  channelName: string;
}

export const VerificationSection: React.FC<VerificationSectionProps> = ({
  verification,
  channelName,
}) => {
  const color = severityColor(verification.discrepancyPercent);
  const label = severityLabel(verification.discrepancyPercent);

  /* Calculate proportional widths — max of the two values is 100% */
  const maxValue = Math.max(verification.platformClaimed, verification.verified);
  const claimedWidth = maxValue > 0 ? (verification.platformClaimed / maxValue) * 100 : 0;
  const verifiedWidth = maxValue > 0 ? (verification.verified / maxValue) * 100 : 0;

  return (
    <section
      role="region"
      aria-label="Revenue verification"
      style={{
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '16px',
            fontWeight: 600,
            color: tokens.text.primary,
            margin: 0,
          }}
        >
          Revenue Verification
        </h3>
        <span
          style={{
            fontFamily: tokens.font.body,
            fontSize: '11px',
            fontWeight: 500,
            color: color,
            padding: '3px 10px',
            borderRadius: '9999px',
            backgroundColor: `${color}18`,
          }}
        >
          {label}
        </span>
      </div>

      {/* Platform Claimed bar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            {channelName} Claimed
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '14px',
              fontWeight: 500,
              color: tokens.text.primary,
            }}
          >
            {verification.platformClaimedFormatted}
          </span>
        </div>
        <div
          style={{
            height: '8px',
            borderRadius: '4px',
            background: tokens.bg.nested,
            overflow: 'hidden',
          }}
        >
          <div
            aria-label={`Platform claimed: ${verification.platformClaimedFormatted}`}
            style={{
              width: `${claimedWidth}%`,
              height: '100%',
              borderRadius: '4px',
              background: `linear-gradient(90deg, ${tokens.text.muted}60, ${tokens.text.muted}90)`,
              transition: `width ${tokens.motion.medium} ease`,
            }}
          />
        </div>
      </div>

      {/* Verified bar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            Verified Revenue
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '14px',
              fontWeight: 500,
              color: tokens.text.primary,
            }}
          >
            {verification.verifiedFormatted}
          </span>
        </div>
        <div
          style={{
            height: '8px',
            borderRadius: '4px',
            background: tokens.bg.nested,
            overflow: 'hidden',
          }}
        >
          <div
            aria-label={`Verified revenue: ${verification.verifiedFormatted}`}
            style={{
              width: `${verifiedWidth}%`,
              height: '100%',
              borderRadius: '4px',
              background: `linear-gradient(90deg, ${color}90, ${color})`,
              transition: `width ${tokens.motion.medium} ease`,
            }}
          />
        </div>
      </div>

      {/* Discrepancy callout */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 16px',
          borderRadius: '6px',
          background: `${color}0A`,
          border: `1px solid ${color}20`,
        }}
      >
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '20px',
            fontWeight: 600,
            color: color,
          }}
        >
          {verification.discrepancyFormatted}
        </span>
        <span
          style={{
            fontFamily: tokens.font.body,
            fontSize: '12px',
            color: tokens.text.secondary,
            lineHeight: 1.4,
          }}
        >
          discrepancy between {channelName} reported and {verification.revenueSource}-verified revenue
        </span>
      </div>

      {/* Footer: source + transaction count */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingTop: '12px',
          borderTop: `1px solid ${tokens.border.subtle}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke={tokens.text.muted}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '11px',
              color: tokens.text.muted,
            }}
          >
            Source: {verification.revenueSource}
          </span>
        </div>
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '11px',
            color: tokens.text.muted,
          }}
        >
          {verification.transactionCountFormatted}
        </span>
      </div>
    </section>
  );
};

export default VerificationSection;
