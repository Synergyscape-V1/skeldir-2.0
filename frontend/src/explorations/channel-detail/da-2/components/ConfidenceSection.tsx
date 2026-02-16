/**
 * DA-2 DOSSIER -- Model Confidence Section
 *
 * Section 04: Large ROAS value with confidence badge, posterior interval,
 * explanation paragraph, evidence citation, and margin display.
 * Every number carries an inline evidence source.
 */
import React, { useEffect } from 'react';
import type { ChannelDetailData, ConfidenceLevel } from '../../shared/types';

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
  text: {
    primary: '#F0F4FF',
    secondary: '#8B9AB8',
    muted: '#4A5568',
  },
  brand: '#3D7BF5',
  confidence: {
    high: '#10D98C',
    medium: '#F5A623',
    low: '#F04E4E',
  } as Record<ConfidenceLevel, string>,
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

const CONFIDENCE_LABELS: Record<ConfidenceLevel, string> = {
  high: 'High Confidence',
  medium: 'Medium Confidence',
  low: 'Low Confidence',
};

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
  heroRow: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 16,
    marginBottom: 12,
    flexWrap: 'wrap' as const,
  } as React.CSSProperties,
  roasValue: {
    fontFamily: FONT.mono,
    fontSize: 36,
    fontWeight: 600,
    color: COLORS.text.primary,
    lineHeight: 1.1,
    margin: 0,
  } as React.CSSProperties,
  confidenceBadge: (level: ConfidenceLevel) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '4px 14px',
    borderRadius: 4,
    background: `${COLORS.confidence[level]}14`,
    border: `1px solid ${COLORS.confidence[level]}33`,
    fontFamily: FONT.body,
    fontSize: 13,
    fontWeight: 500,
    color: COLORS.confidence[level],
    letterSpacing: 0.5,
  } as React.CSSProperties),
  dot: (level: ConfidenceLevel) => ({
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: COLORS.confidence[level],
    flexShrink: 0,
  } as React.CSSProperties),
  rangeText: {
    fontFamily: FONT.mono,
    fontSize: 14,
    fontWeight: 500,
    color: COLORS.text.secondary,
    margin: '0 0 16px',
    lineHeight: 1.6,
  } as React.CSSProperties,
  explanation: {
    fontFamily: FONT.body,
    fontSize: 14,
    fontWeight: 400,
    color: COLORS.text.secondary,
    lineHeight: 1.7,
    margin: '0 0 16px',
    maxWidth: 640,
  } as React.CSSProperties,
  citationRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    flexWrap: 'wrap' as const,
    padding: '12px 16px',
    background: COLORS.nestedBg,
    borderRadius: 4,
    border: `1px solid ${COLORS.border.subtle}`,
  } as React.CSSProperties,
  citationText: {
    fontFamily: FONT.body,
    fontSize: 12,
    fontWeight: 400,
    color: COLORS.text.muted,
    fontStyle: 'italic' as const,
    lineHeight: 1.5,
    margin: 0,
  } as React.CSSProperties,
  marginBadge: (level: ConfidenceLevel) => ({
    fontFamily: FONT.mono,
    fontSize: 13,
    fontWeight: 600,
    color: COLORS.confidence[level],
    padding: '4px 10px',
    borderRadius: 4,
    background: `${COLORS.confidence[level]}14`,
    border: `1px solid ${COLORS.confidence[level]}33`,
    whiteSpace: 'nowrap' as const,
  } as React.CSSProperties),
} as const;

/* ── Component ────────────────────────────────────────────── */
interface ConfidenceSectionProps {
  confidenceRange: ChannelDetailData['confidenceRange'];
}

export const ConfidenceSection: React.FC<ConfidenceSectionProps> = ({ confidenceRange }) => {
  useEffect(() => {
    ensureFonts();
  }, []);

  const {
    pointFormatted,
    lowFormatted,
    highFormatted,
    level,
    explanation,
    margin,
    daysOfData,
    conversionsUsed,
  } = confidenceRange;

  return (
    <section style={styles.wrapper} aria-labelledby="da2-section-confidence">
      {/* Section label bar */}
      <div style={styles.sectionLabel}>
        <span style={styles.sectionNumber}>04</span>
        <span id="da2-section-confidence" style={styles.sectionTitle}>
          Model Confidence
        </span>
        <div style={styles.dividerLine} aria-hidden="true" />
      </div>

      {/* Hero: ROAS value + confidence badge */}
      <div style={styles.heroRow}>
        <p style={styles.roasValue}>{pointFormatted}</p>
        <span style={styles.confidenceBadge(level)}>
          <span style={styles.dot(level)} aria-hidden="true" />
          {CONFIDENCE_LABELS[level]}
        </span>
      </div>

      {/* Posterior interval */}
      <p style={styles.rangeText}>
        Between {lowFormatted} and {highFormatted} (90% posterior interval)
      </p>

      {/* Explanation paragraph */}
      <p style={styles.explanation}>{explanation}</p>

      {/* Evidence citation + margin */}
      <div style={styles.citationRow}>
        <p style={styles.citationText}>
          Based on {daysOfData.toLocaleString()} days of data and{' '}
          {conversionsUsed.toLocaleString()} conversions
        </p>
        <span style={styles.marginBadge(level)} title="Model margin of error">
          &plusmn;{margin}%
        </span>
      </div>
    </section>
  );
};

export default ConfidenceSection;
