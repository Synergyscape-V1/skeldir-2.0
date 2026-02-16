/**
 * DA-5 COMPACT — Minimal channel header
 *
 * Centered channel name with platform color dot, status, and date range.
 * Generous whitespace, minimal chrome.
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';
import { CHANNEL_COLORS } from '../../shared/types';

/* ── Design tokens ─────────────────────────────────────────────── */
const T = {
  textPrimary: '#F0F4FF',
  textSecondary: '#8B9AB8',
  textMuted: '#4A5568',
  fontHeading: "'Syne', sans-serif",
  fontBody: "'IBM Plex Sans', sans-serif",
};

interface ChannelHeaderProps {
  channel: ChannelDetailData['channel'];
  dateRange: ChannelDetailData['dateRange'];
}

export const ChannelHeader: React.FC<ChannelHeaderProps> = ({
  channel,
  dateRange,
}) => {
  const platformColor = CHANNEL_COLORS[channel.platform] || CHANNEL_COLORS['other'];

  const statusLabel: Record<string, string> = {
    active: 'Active',
    paused: 'Paused',
    disconnected: 'Disconnected',
  };

  return (
    <div
      style={{
        textAlign: 'center',
        padding: '32px 0 24px',
      }}
    >
      {/* Channel name + platform dot */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: platformColor,
            display: 'inline-block',
            flexShrink: 0,
          }}
          aria-hidden="true"
        />
        <h1
          style={{
            fontFamily: T.fontHeading,
            fontWeight: 600,
            fontSize: 20,
            color: T.textPrimary,
            margin: 0,
            lineHeight: 1.3,
            letterSpacing: '-0.01em',
          }}
        >
          {channel.name}
        </h1>
      </div>

      {/* Status */}
      <p
        style={{
          fontFamily: T.fontBody,
          fontSize: 12,
          fontWeight: 400,
          color: T.textSecondary,
          margin: '6px 0 0',
          lineHeight: 1.4,
        }}
      >
        {statusLabel[channel.status] || channel.status}
      </p>

      {/* Date range */}
      <p
        style={{
          fontFamily: T.fontBody,
          fontSize: 12,
          fontWeight: 400,
          color: T.textMuted,
          margin: '4px 0 0',
          lineHeight: 1.4,
        }}
      >
        {dateRange.label}
      </p>
    </div>
  );
};
