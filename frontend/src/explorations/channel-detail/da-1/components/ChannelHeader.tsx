/**
 * DA-1 COCKPIT — Channel Header
 *
 * Top-row instrument panel: channel name, platform indicator dot,
 * status badge, date range, and model info.
 *
 * All values arrive pre-formatted from ChannelDetailData.
 * No client-side calculations.
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';
import { CHANNEL_COLORS } from '../../shared/types';

/* ── Design Tokens (inline) ─────────────────────────────────────── */
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
  brand: '#3D7BF5',
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

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: 'Active', color: '#10D98C', bg: 'rgba(16,217,140,0.12)' },
  paused: { label: 'Paused', color: '#F5A623', bg: 'rgba(245,166,35,0.12)' },
  disconnected: { label: 'Disconnected', color: '#F04E4E', bg: 'rgba(240,78,78,0.12)' },
};

interface ChannelHeaderProps {
  channel: ChannelDetailData['channel'];
  dateRange: ChannelDetailData['dateRange'];
  modelInfo: ChannelDetailData['modelInfo'];
}

export const ChannelHeader: React.FC<ChannelHeaderProps> = ({
  channel,
  dateRange,
  modelInfo,
}) => {
  const platformColor = CHANNEL_COLORS[channel.platform] || CHANNEL_COLORS['other'];
  const statusInfo = STATUS_MAP[channel.status] || STATUS_MAP['disconnected'];

  return (
    <div
      role="banner"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        padding: '20px 24px',
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
      }}
    >
      {/* Left: Channel identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Platform color dot */}
        <div
          aria-hidden="true"
          style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: platformColor,
            boxShadow: `0 0 8px ${platformColor}40`,
            flexShrink: 0,
          }}
        />

        <div>
          <h1
            style={{
              fontFamily: tokens.font.heading,
              fontSize: '24px',
              fontWeight: 600,
              color: tokens.text.primary,
              margin: 0,
              lineHeight: 1.3,
            }}
          >
            {channel.name}
          </h1>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.muted,
            }}
          >
            Connected since {channel.connectedSince}
          </span>
        </div>

        {/* Status badge */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 12px',
            borderRadius: '9999px',
            backgroundColor: statusInfo.bg,
            fontFamily: tokens.font.body,
            fontSize: '12px',
            fontWeight: 500,
            color: statusInfo.color,
            lineHeight: 1,
          }}
        >
          <span
            aria-hidden="true"
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: statusInfo.color,
            }}
          />
          {statusInfo.label}
        </span>
      </div>

      {/* Right: Date range + model info */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '24px',
          flexWrap: 'wrap',
        }}
      >
        {/* Date range */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            background: tokens.bg.nested,
            borderRadius: '6px',
            border: `1px solid ${tokens.border.subtle}`,
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke={tokens.text.secondary}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '14px',
              color: tokens.text.primary,
            }}
          >
            {dateRange.label}
          </span>
        </div>

        {/* Model info */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            gap: '2px',
          }}
        >
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            Model v{modelInfo.version}
          </span>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.muted,
            }}
          >
            Updated {modelInfo.lastUpdatedFormatted} · Next {modelInfo.nextUpdate}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ChannelHeader;
