/**
 * DA-1 COCKPIT — Verification Section
 *
 * Platform vs Verified revenue comparison instrument panel.
 * Two horizontal bars, gap visualization, discrepancy percentage.
 *
 * Color severity thresholds:
 *   green (<5%) — within expected variance
 *   amber (5-15%) — worth investigating
 *   red (>15%) — significant discrepancy
 *
 * All values pre-formatted. No client-side calculations.
 */

import React, { useId } from 'react';
import type { ChannelDetailData } from '../../shared/types';

/* ── Design Tokens ──────────────────────────────────────────────── */
const tokens = {
  bg: {
    card: '#111827',
    nested: '#1F2937',
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
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
} as const;

function getDiscrepancyColor(pct: number): string {
  const absPct = Math.abs(pct);
  if (absPct < 5) return tokens.confidence.high;
  if (absPct < 15) return tokens.confidence.medium;
  return tokens.confidence.low;
}

function getDiscrepancyLabel(pct: number): string {
  const absPct = Math.abs(pct);
  if (absPct < 5) return 'Within expected variance';
  if (absPct < 15) return 'Worth investigating';
  return 'Significant discrepancy';
}

interface VerificationSectionProps {
  verification: ChannelDetailData['verification'];
}

export const VerificationSection: React.FC<VerificationSectionProps> = ({
  verification,
}) => {
  const sectionId = useId();
  const discColor = getDiscrepancyColor(verification.discrepancyPercent);
  const discLabel = getDiscrepancyLabel(verification.discrepancyPercent);

  // Bar widths: platform claimed is always 100%, verified is proportional
  const maxValue = Math.max(verification.platformClaimed, verification.verified);
  const platformPct = (verification.platformClaimed / maxValue) * 100;
  const verifiedPct = (verification.verified / maxValue) * 100;

  return (
    <section
      aria-labelledby={sectionId}
      style={{
        padding: '24px',
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <h3
          id={sectionId}
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '20px',
            fontWeight: 600,
            color: tokens.text.primary,
            margin: 0,
          }}
        >
          Revenue Verification
        </h3>

        {/* Verified by source badge */}
        <span
          style={{
            fontFamily: tokens.font.body,
            fontSize: '12px',
            color: tokens.text.secondary,
            padding: '4px 12px',
            background: tokens.bg.nested,
            borderRadius: '4px',
            border: `1px solid ${tokens.border.subtle}`,
          }}
        >
          Verified by {verification.revenueSource}
        </span>
      </div>

      {/* Discrepancy hero */}
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '12px',
        }}
      >
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '36px',
            fontWeight: 600,
            color: discColor,
            lineHeight: 1,
          }}
        >
          {verification.discrepancyFormatted}
        </span>
        <span
          style={{
            fontFamily: tokens.font.body,
            fontSize: '14px',
            color: discColor,
            fontWeight: 500,
          }}
        >
          {discLabel}
        </span>
      </div>

      {/* Bar comparison */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Platform claimed bar */}
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '6px',
            }}
          >
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '12px',
                color: tokens.text.secondary,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              Platform Claimed
            </span>
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '14px',
                color: tokens.text.primary,
                fontWeight: 500,
              }}
            >
              {verification.platformClaimedFormatted}
            </span>
          </div>
          <div
            style={{
              height: '12px',
              borderRadius: '6px',
              backgroundColor: tokens.bg.nested,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${platformPct}%`,
                borderRadius: '6px',
                backgroundColor: `${tokens.text.secondary}60`,
                transition: 'width 300ms cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            />
          </div>
        </div>

        {/* Verified bar */}
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '6px',
            }}
          >
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '12px',
                color: tokens.text.secondary,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              Verified Revenue
            </span>
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '14px',
                color: tokens.text.primary,
                fontWeight: 500,
              }}
            >
              {verification.verifiedFormatted}
            </span>
          </div>
          <div
            style={{
              height: '12px',
              borderRadius: '6px',
              backgroundColor: tokens.bg.nested,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${verifiedPct}%`,
                borderRadius: '6px',
                backgroundColor: discColor,
                transition: 'width 300ms cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            />
          </div>
        </div>

        {/* Gap visualization line */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 0',
          }}
        >
          <div
            style={{
              flex: 1,
              height: '1px',
              background: `repeating-linear-gradient(90deg, ${discColor}60 0, ${discColor}60 4px, transparent 4px, transparent 8px)`,
            }}
          />
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              color: discColor,
              whiteSpace: 'nowrap',
            }}
          >
            Gap: {verification.discrepancyFormatted}
          </span>
          <div
            style={{
              flex: 1,
              height: '1px',
              background: `repeating-linear-gradient(90deg, ${discColor}60 0, ${discColor}60 4px, transparent 4px, transparent 8px)`,
            }}
          />
        </div>
      </div>

      {/* Footer stats */}
      <div
        style={{
          display: 'flex',
          gap: '24px',
          padding: '12px 16px',
          background: tokens.bg.nested,
          borderRadius: '6px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.muted,
            }}
          >
            Transactions matched
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '14px',
              fontWeight: 500,
              color: tokens.text.primary,
            }}
          >
            {verification.transactionCountFormatted}
          </span>
        </div>
      </div>
    </section>
  );
};

export default VerificationSection;
