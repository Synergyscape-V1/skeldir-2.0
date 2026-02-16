/**
 * DA-5 COMPACT — Verification section (expandable)
 *
 * Collapsed: "Revenue verified - -5.2% discrepancy" with severity dot
 * Expanded: platform claimed vs verified, transaction count, revenue source
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';

/* ── Design tokens ─────────────────────────────────────────────── */
const T = {
  textPrimary: '#F0F4FF',
  textSecondary: '#8B9AB8',
  textMuted: '#4A5568',
  high: '#10D98C',
  medium: '#F5A623',
  low: '#F04E4E',
  nested: '#1F2937',
  borderSubtle: 'rgba(139,154,184,0.12)',
  fontBody: "'IBM Plex Sans', sans-serif",
  fontData: "'IBM Plex Mono', monospace",
};

interface VerificationSectionProps {
  verification: ChannelDetailData['verification'];
  channelName: string;
}

/** Return severity color based on absolute discrepancy percent */
function severityColor(discrepancyPercent: number): string {
  const abs = Math.abs(discrepancyPercent);
  if (abs <= 5) return T.high;
  if (abs <= 15) return T.medium;
  return T.low;
}

export const VerificationSection: React.FC<VerificationSectionProps> = ({
  verification,
  channelName,
}) => {
  const color = severityColor(verification.discrepancyPercent);

  return (
    <div style={{ padding: '16px 0' }}>
      {/* Summary line */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 20,
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily: T.fontBody,
            fontSize: 14,
            fontWeight: 500,
            color: T.textPrimary,
          }}
        >
          Revenue verified
        </span>
        <span
          style={{
            fontFamily: T.fontData,
            fontSize: 13,
            fontWeight: 400,
            color: color,
          }}
        >
          {verification.discrepancyFormatted} discrepancy
        </span>
      </div>

      {/* Comparison rows */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        {/* Platform claimed */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 16px',
            background: T.nested,
            borderRadius: 8,
          }}
        >
          <div>
            <p
              style={{
                fontFamily: T.fontBody,
                fontSize: 11,
                color: T.textMuted,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                margin: 0,
              }}
            >
              {channelName} reported
            </p>
          </div>
          <p
            style={{
              fontFamily: T.fontData,
              fontSize: 18,
              fontWeight: 500,
              color: T.textSecondary,
              margin: 0,
            }}
          >
            {verification.platformClaimedFormatted}
          </p>
        </div>

        {/* Verified */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 16px',
            background: T.nested,
            borderRadius: 8,
          }}
        >
          <div>
            <p
              style={{
                fontFamily: T.fontBody,
                fontSize: 11,
                color: T.textMuted,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                margin: 0,
              }}
            >
              Verified via {verification.revenueSource}
            </p>
          </div>
          <p
            style={{
              fontFamily: T.fontData,
              fontSize: 18,
              fontWeight: 600,
              color: T.textPrimary,
              margin: 0,
            }}
          >
            {verification.verifiedFormatted}
          </p>
        </div>

        {/* Discrepancy + transaction count */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '10px 16px',
            borderTop: `1px solid ${T.borderSubtle}`,
          }}
        >
          <span
            style={{
              fontFamily: T.fontBody,
              fontSize: 12,
              color: T.textSecondary,
            }}
          >
            Discrepancy
          </span>
          <span
            style={{
              fontFamily: T.fontData,
              fontSize: 14,
              fontWeight: 600,
              color: color,
            }}
          >
            {verification.discrepancyFormatted}
          </span>
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0 16px 4px',
          }}
        >
          <span
            style={{
              fontFamily: T.fontBody,
              fontSize: 12,
              color: T.textSecondary,
            }}
          >
            Transactions matched
          </span>
          <span
            style={{
              fontFamily: T.fontData,
              fontSize: 14,
              fontWeight: 500,
              color: T.textPrimary,
            }}
          >
            {verification.transactionCountFormatted}
          </span>
        </div>
      </div>
    </div>
  );
};
