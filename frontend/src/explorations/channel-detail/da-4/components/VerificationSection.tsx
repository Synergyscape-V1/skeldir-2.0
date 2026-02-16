/**
 * DA-4 ANALYST — Verification Section (TRUST ANCHOR)
 *
 * The most prominent section in the right panel.
 * Ledger-style rows showing Platform Claims vs Verified Revenue vs Discrepancy.
 * Left colored border encodes severity (green <5%, amber 5-15%, red >15%).
 * Monospace values throughout, revenue source attribution.
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';

/* ── Design Tokens ──────────────────────────────────────────────── */
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
  confidence: {
    high: '#10D98C',
    medium: '#F5A623',
    low: '#F04E4E',
  },
  border: {
    subtle: 'rgba(139,154,184,0.12)',
    default: 'rgba(139,154,184,0.24)',
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  motion: {
    short: '200ms',
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
} as const;

/* ── Severity color logic ────────────────────────────────────────── */
function getSeverityColor(discrepancyPercent: number): string {
  const abs = Math.abs(discrepancyPercent);
  if (abs > 15) return tokens.confidence.low;
  if (abs >= 5) return tokens.confidence.medium;
  return tokens.confidence.high;
}

/* ── Props ──────────────────────────────────────────────────────── */
interface VerificationSectionProps {
  verification: ChannelDetailData['verification'];
  channelName: string;
}

/* ── Component ──────────────────────────────────────────────────── */
export const VerificationSection: React.FC<VerificationSectionProps> = ({
  verification,
  channelName,
}) => {
  const severityColor = getSeverityColor(verification.discrepancyPercent);

  return (
    <>
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>
      <div
        style={{
          backgroundColor: tokens.bg.card,
          border: `1px solid ${tokens.border.subtle}`,
          borderLeft: `3px solid ${severityColor}`,
          borderRadius: '8px',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
        }}
        role="region"
        aria-label={`Revenue verification for ${channelName}`}
      >
        {/* Section heading */}
        <h2
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '16px',
            fontWeight: 600,
            color: tokens.text.primary,
            margin: 0,
            letterSpacing: '-0.01em',
          }}
        >
          Revenue Verification
        </h2>

        {/* Ledger rows */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0',
          }}
        >
          {/* Platform Claims */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 0',
              borderBottom: `1px solid ${tokens.border.subtle}`,
            }}
          >
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '13px',
                fontWeight: 400,
                color: tokens.text.secondary,
              }}
            >
              Platform Claims
            </span>
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '16px',
                fontWeight: 500,
                color: tokens.text.secondary,
              }}
            >
              {verification.platformClaimedFormatted}
            </span>
          </div>

          {/* Verified Revenue */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 0',
              borderBottom: `1px solid ${tokens.border.subtle}`,
            }}
          >
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '13px',
                fontWeight: 500,
                color: tokens.text.primary,
              }}
            >
              Verified Revenue
            </span>
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '18px',
                fontWeight: 600,
                color: tokens.text.primary,
              }}
            >
              {verification.verifiedFormatted}
            </span>
          </div>

          {/* Discrepancy */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 0',
              borderBottom: `1px solid ${tokens.border.subtle}`,
            }}
          >
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '13px',
                fontWeight: 400,
                color: tokens.text.secondary,
              }}
            >
              Discrepancy
            </span>
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '16px',
                fontWeight: 600,
                color: severityColor,
              }}
            >
              {verification.discrepancyFormatted}
            </span>
          </div>
        </div>

        {/* Revenue source + transaction count */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            {/* Shield icon */}
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke={tokens.confidence.high}
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
                fontSize: '12px',
                fontWeight: 500,
                color: tokens.text.secondary,
              }}
            >
              Verified by{' '}
              <span style={{ color: tokens.text.primary, fontWeight: 600 }}>
                {verification.revenueSource}
              </span>
            </span>
          </div>

          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '11px',
              fontWeight: 400,
              color: tokens.text.muted,
            }}
          >
            {verification.transactionCountFormatted}
          </span>
        </div>
      </div>
    </>
  );
};

export default VerificationSection;
