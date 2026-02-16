/**
 * DA-3 TIMELINE — Channel Header
 *
 * Compact info bar at top of the timeline page.
 * Channel name with platform color dot, status badge, and date range.
 * Deliberately compact so the timeline ribbon below gets maximum real estate.
 *
 * All values arrive pre-formatted from ChannelDetailData.
 * No client-side calculations.
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';
import { CHANNEL_COLORS } from '../../shared/types';

/* ── Design Tokens ─────────────────────────────────────────────── */
const tokens = {
  bg: {
    page: '#0A0E1A',
    card: '#111827',
    nested: '#1F2937',
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
    micro: '120ms',
    short: '200ms',
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
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        padding: '16px 24px',
        background: `linear-gradient(135deg, ${tokens.bg.card} 0%, rgba(17,24,39,0.85) 100%)`,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        backdropFilter: 'blur(8px)',
      }}
    >
      {/* Left: Channel identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Platform color dot with glow */}
        <div
          aria-hidden="true"
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            backgroundColor: platformColor,
            boxShadow: `0 0 10px ${platformColor}50, 0 0 4px ${platformColor}30`,
            flexShrink: 0,
          }}
        />

        <h1
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '20px',
            fontWeight: 600,
            color: tokens.text.primary,
            margin: 0,
            lineHeight: 1.3,
          }}
        >
          {channel.name}
        </h1>

        {/* Status badge */}
        <span
          role="status"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            padding: '3px 10px',
            borderRadius: '9999px',
            backgroundColor: statusInfo.bg,
            fontFamily: tokens.font.body,
            fontSize: '11px',
            fontWeight: 500,
            color: statusInfo.color,
            lineHeight: 1,
            letterSpacing: '0.02em',
          }}
        >
          <span
            aria-hidden="true"
            style={{
              width: '5px',
              height: '5px',
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
          gap: '20px',
          flexWrap: 'wrap',
        }}
      >
        {/* Date range pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 12px',
            background: tokens.bg.nested,
            borderRadius: '6px',
            border: `1px solid ${tokens.border.subtle}`,
          }}
        >
          <svg
            width="12"
            height="12"
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
              fontSize: '12px',
              color: tokens.text.primary,
            }}
          >
            {dateRange.label}
          </span>
        </div>

        {/* Model version */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '11px',
              color: tokens.text.muted,
            }}
          >
            v{modelInfo.version}
          </span>
          <span
            style={{
              width: '1px',
              height: '12px',
              backgroundColor: tokens.border.default,
            }}
            aria-hidden="true"
          />
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '11px',
              color: tokens.text.muted,
            }}
          >
            Updated {modelInfo.lastUpdatedFormatted}
          </span>
        </div>
      </div>
    </header>
  );
};

export default ChannelHeader;
