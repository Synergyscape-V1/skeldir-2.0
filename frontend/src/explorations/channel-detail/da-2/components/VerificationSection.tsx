/**
 * DA-2 DOSSIER -- Revenue Verification Section
 *
 * Section 03: Ledger-style row display comparing platform-claimed revenue
 * against verified (Stripe) revenue, with discrepancy severity coloring
 * and evidence citation. Styled as an intelligence document ledger.
 */
import React, { useEffect } from 'react';
import type { ChannelDetailData } from '../../shared/types';

/* ── Google Fonts ─────────────────────────────────────────── */
const FONT_LINK_ID = 'da2-google-fonts';
function ensureFonts() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(FONT_LINK_ID)) return;
  const link = document.createElement('link');
  link.id = FONT_LINK_ID;
  link.rel = 'stylesheet';
  link.href =
    'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=Syne:wght@500;600;700&display=swap';
  document.head.appendChild(link);
}

/* ── Design Tokens ────────────────────────────────────────── */
const COLORS = {
  pageBg: '#0A0E1A',
  cardBg: '#111827',
  nestedBg: '#1F2937',
  elevated: '#263244',
  text: {
    primary: '#F0F4FF',
    secondary: '#8B9AB8',
    muted: '#4A5568',
  },
  brand: '#3D7BF5',
  severity: {
    low: '#10D98C',    // <5% discrepancy
    medium: '#F5A623', // 5-15%
    high: '#F04E4E',   // >15%
  },
  border: {
    subtle: 'rgba(139,154,184,0.12)',
    default: 'rgba(139,154,184,0.24)',
  },
} as const;

const FONT = {
  heading: "'Syne', sans-serif",
  body: "'IBM Plex Sans', sans-serif",
  mono: "'IBM Plex Mono', monospace",
} as const;

/* ── Severity logic ──────────────────────────────────────── */
function getSeverityColor(discrepancyPercent: number): string {
  const abs = Math.abs(discrepancyPercent);
  if (abs < 5) return COLORS.severity.low;
  if (abs <= 15) return COLORS.severity.medium;
  return COLORS.severity.high;
}

function getSeverityLabel(discrepancyPercent: number): string {
  const abs = Math.abs(discrepancyPercent);
  if (abs < 5) return 'Within expected range';
  if (abs <= 15) return 'Elevated discrepancy';
  return 'Significant discrepancy';
}

/* ── Styles ───────────────────────────────────────────────── */
const styles = {
  wrapper: {
    padding: '32px 0 24px',
    borderBottom: `1px solid ${COLORS.border.subtle}`,
  } as React.CSSProperties,
  sectionLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginBottom: 24,
  } as React.CSSProperties,
  sectionNumber: {
    fontFamily: FONT.mono,
    fontSize: 11,
    fontWeight: 600,
    color: COLORS.text.muted,
    letterSpacing: 2,
    textTransform: 'uppercase' as const,
    minWidth: 32,
  } as React.CSSProperties,
  sectionTitle: {
    fontFamily: FONT.heading,
    fontSize: 11,
    fontWeight: 600,
    color: COLORS.text.muted,
    letterSpacing: 3,
    textTransform: 'uppercase' as const,
  } as React.CSSProperties,
  dividerLine: {
    flex: 1,
    height: 1,
    background: COLORS.border.subtle,
  } as React.CSSProperties,
  ledger: (severityColor: string) => ({
    background: COLORS.nestedBg,
    border: `1px solid ${COLORS.border.subtle}`,
    borderLeft: `3px solid ${severityColor}`,
    borderRadius: '0 6px 6px 0',
    padding: 0,
    overflow: 'hidden',
  } as React.CSSProperties),
  ledgerRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '14px 24px',
    borderBottom: `1px solid ${COLORS.border.subtle}`,
  } as React.CSSProperties,
  ledgerRowLast: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '14px 24px',
  } as React.CSSProperties,
  ledgerLabel: {
    fontFamily: FONT.body,
    fontSize: 14,
    fontWeight: 500,
    color: COLORS.text.secondary,
    margin: 0,
  } as React.CSSProperties,
  ledgerValue: {
    fontFamily: FONT.mono,
    fontSize: 16,
    fontWeight: 600,
    color: COLORS.text.primary,
    margin: 0,
  } as React.CSSProperties,
  discrepancyValue: (color: string) => ({
    fontFamily: FONT.mono,
    fontSize: 16,
    fontWeight: 600,
    color,
    margin: 0,
  } as React.CSSProperties),
  severityBadge: (color: string) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '3px 10px',
    borderRadius: 4,
    background: `${color}14`,
    border: `1px solid ${color}33`,
    fontFamily: FONT.body,
    fontSize: 11,
    fontWeight: 500,
    color,
    letterSpacing: 0.5,
    marginLeft: 12,
  } as React.CSSProperties),
  evidenceRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
    padding: '10px 16px',
    background: COLORS.cardBg,
    borderRadius: 4,
    border: `1px solid ${COLORS.border.subtle}`,
  } as React.CSSProperties,
  evidenceText: {
    fontFamily: FONT.body,
    fontSize: 12,
    fontWeight: 400,
    color: COLORS.text.muted,
    fontStyle: 'italic' as const,
    lineHeight: 1.5,
    margin: 0,
  } as React.CSSProperties,
  evidenceSource: {
    fontFamily: FONT.mono,
    fontSize: 12,
    fontWeight: 500,
    color: COLORS.text.secondary,
  } as React.CSSProperties,
} as const;

/* ── Component ────────────────────────────────────────────── */
interface VerificationSectionProps {
  verification: ChannelDetailData['verification'];
  channelName: string;
}

export const VerificationSection: React.FC<VerificationSectionProps> = ({
  verification,
  channelName,
}) => {
  useEffect(() => {
    ensureFonts();
  }, []);

  const {
    platformClaimedFormatted,
    verifiedFormatted,
    discrepancyPercent,
    discrepancyFormatted,
    transactionCountFormatted,
    revenueSource,
  } = verification;

  const severityColor = getSeverityColor(discrepancyPercent);
  const severityLabel = getSeverityLabel(discrepancyPercent);

  return (
    <section style={styles.wrapper} aria-labelledby="da2-section-verification">
      {/* Section label bar */}
      <div style={styles.sectionLabel}>
        <span style={styles.sectionNumber}>03</span>
        <span id="da2-section-verification" style={styles.sectionTitle}>
          Revenue Verification
        </span>
        <div style={styles.dividerLine} aria-hidden="true" />
      </div>

      {/* Ledger */}
      <div style={styles.ledger(severityColor)} role="table" aria-label="Revenue verification ledger">
        {/* Platform claimed */}
        <div style={styles.ledgerRow} role="row">
          <span style={styles.ledgerLabel} role="cell">
            {channelName} Claims
          </span>
          <span style={styles.ledgerValue} role="cell">
            {platformClaimedFormatted}
          </span>
        </div>

        {/* Verified */}
        <div style={styles.ledgerRow} role="row">
          <span style={styles.ledgerLabel} role="cell">
            {revenueSource} Verified
          </span>
          <span style={styles.ledgerValue} role="cell">
            {verifiedFormatted}
          </span>
        </div>

        {/* Discrepancy */}
        <div style={styles.ledgerRowLast} role="row">
          <span style={styles.ledgerLabel} role="cell">
            Discrepancy
          </span>
          <span style={{ display: 'flex', alignItems: 'center' }}>
            <span style={styles.discrepancyValue(severityColor)} role="cell">
              {discrepancyFormatted}
            </span>
            <span style={styles.severityBadge(severityColor)}>
              {severityLabel}
            </span>
          </span>
        </div>
      </div>

      {/* Evidence citation */}
      <div style={styles.evidenceRow}>
        <p style={styles.evidenceText}>
          Cross-referenced against{' '}
          <span style={styles.evidenceSource}>{transactionCountFormatted}</span>
          {' '}via {revenueSource}
        </p>
      </div>
    </section>
  );
};

export default VerificationSection;
