/**
 * DA-2 DOSSIER — Channel Header / Channel Brief
 *
 * Document-style header: "CHANNEL BRIEF" section label, channel name
 * as primary heading, platform badge, status, connected-since date stamp.
 * Section 01 of the intelligence dossier.
 */
import React from 'react';
import type { ChannelDetailData } from '../../shared/types';
import { CHANNEL_COLORS } from '../../shared/types';

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

/* ── Status config ────────────────────────────────────────── */
const STATUS_MAP: Record<string, { label: string; color: string }> = {
  active: { label: 'Active', color: '#10D98C' },
  paused: { label: 'Paused', color: '#F5A623' },
  disconnected: { label: 'Disconnected', color: '#F04E4E' },
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
    marginBottom: 20,
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
  channelName: {
    fontFamily: FONT.heading,
    fontSize: 24,
    fontWeight: 600,
    color: COLORS.text.primary,
    margin: '0 0 16px',
    lineHeight: 1.3,
  } as React.CSSProperties,
  metaRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    flexWrap: 'wrap' as const,
  } as React.CSSProperties,
  badge: (color: string) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 12px',
    borderRadius: 4,
    background: `${color}14`,
    border: `1px solid ${color}33`,
    fontFamily: FONT.body,
    fontSize: 12,
    fontWeight: 500,
    color,
    letterSpacing: 0.5,
  } as React.CSSProperties),
  statusDot: (color: string) => ({
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: color,
    flexShrink: 0,
  } as React.CSSProperties),
  metaLabel: {
    fontFamily: FONT.body,
    fontSize: 12,
    color: COLORS.text.muted,
  } as React.CSSProperties,
  metaValue: {
    fontFamily: FONT.mono,
    fontSize: 12,
    color: COLORS.text.secondary,
  } as React.CSSProperties,
  dateStamp: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
    padding: '8px 16px',
    background: COLORS.nestedBg,
    borderRadius: 4,
    border: `1px solid ${COLORS.border.subtle}`,
    width: 'fit-content',
  } as React.CSSProperties,
  dateLabel: {
    fontFamily: FONT.body,
    fontSize: 11,
    fontWeight: 500,
    color: COLORS.text.muted,
    letterSpacing: 1,
    textTransform: 'uppercase' as const,
  } as React.CSSProperties,
  dateValue: {
    fontFamily: FONT.mono,
    fontSize: 13,
    fontWeight: 500,
    color: COLORS.text.primary,
  } as React.CSSProperties,
} as const;

/* ── Component ────────────────────────────────────────────── */
interface ChannelHeaderProps {
  channel: ChannelDetailData['channel'];
  dateRange: ChannelDetailData['dateRange'];
}

const ChannelHeader: React.FC<ChannelHeaderProps> = ({ channel, dateRange }) => {
  const statusConfig = STATUS_MAP[channel.status] ?? STATUS_MAP.active;
  const channelColor = CHANNEL_COLORS[channel.platform] ?? CHANNEL_COLORS.other;
  const connectedDate = new Date(channel.connectedSince).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <section style={styles.wrapper} aria-labelledby="da2-section-brief">
      {/* Section label bar */}
      <div style={styles.sectionLabel}>
        <span style={styles.sectionNumber}>01</span>
        <span id="da2-section-brief" style={styles.sectionTitle}>Channel Brief</span>
        <div style={styles.dividerLine} aria-hidden="true" />
      </div>

      {/* Channel name */}
      <h1 style={styles.channelName}>{channel.name}</h1>

      {/* Meta row: platform badge, status, connected since */}
      <div style={styles.metaRow}>
        <span style={styles.badge(channelColor)}>
          {channel.platform.charAt(0).toUpperCase() + channel.platform.slice(1)}
        </span>

        <span style={styles.badge(statusConfig.color)}>
          <span style={styles.statusDot(statusConfig.color)} aria-hidden="true" />
          {statusConfig.label}
        </span>

        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={styles.metaLabel}>Connected since</span>
          <span style={styles.metaValue}>{connectedDate}</span>
        </span>
      </div>

      {/* Date range stamp */}
      <div style={styles.dateStamp}>
        <span style={styles.dateLabel}>Report Period</span>
        <span style={styles.dateValue}>{dateRange.label}</span>
      </div>
    </section>
  );
};

export default ChannelHeader;
