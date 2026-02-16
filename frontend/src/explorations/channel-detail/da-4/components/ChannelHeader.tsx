/**
 * DA-4 ANALYST — Channel Header
 *
 * Full-width header with IDE-style breadcrumb navigation.
 * Shows channel name, platform color dot, status badge, and date range.
 * Developer-tool aesthetic with monospace accents.
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';
import { CHANNEL_COLORS } from '../../shared/types';

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
  brand: '#3D7BF5',
  status: {
    active: '#10D98C',
    paused: '#F5A623',
    disconnected: '#F04E4E',
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

const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  paused: 'Paused',
  disconnected: 'Disconnected',
};

/* ── Props ──────────────────────────────────────────────────────── */
interface ChannelHeaderProps {
  channel: ChannelDetailData['channel'];
  dateRange: ChannelDetailData['dateRange'];
}

/* ── Component ──────────────────────────────────────────────────── */
export const ChannelHeader: React.FC<ChannelHeaderProps> = ({ channel, dateRange }) => {
  const platformColor = CHANNEL_COLORS[channel.platform.toLowerCase()] || CHANNEL_COLORS['other'];
  const statusColor = tokens.status[channel.status] || tokens.status.disconnected;
  const statusLabel = STATUS_LABELS[channel.status] || channel.status;

  return (
    <>
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          padding: '20px 0',
          borderBottom: `1px solid ${tokens.border.subtle}`,
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        {/* Left: Breadcrumb + Channel Name */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {/* Breadcrumb */}
          <nav aria-label="Breadcrumb">
            <ol
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                listStyle: 'none',
                margin: 0,
                padding: 0,
              }}
            >
              <li>
                <span
                  style={{
                    fontFamily: tokens.font.mono,
                    fontSize: '12px',
                    color: tokens.text.muted,
                    letterSpacing: '0.02em',
                  }}
                >
                  Channels
                </span>
              </li>
              <li aria-hidden="true">
                <span
                  style={{
                    fontFamily: tokens.font.mono,
                    fontSize: '12px',
                    color: tokens.text.muted,
                  }}
                >
                  /
                </span>
              </li>
              <li>
                <span
                  style={{
                    fontFamily: tokens.font.mono,
                    fontSize: '12px',
                    color: tokens.text.secondary,
                  }}
                >
                  {channel.name}
                </span>
              </li>
            </ol>
          </nav>

          {/* Channel Name + Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Platform color dot */}
            <div
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: platformColor,
                flexShrink: 0,
              }}
              aria-hidden="true"
            />

            {/* Channel name */}
            <h1
              style={{
                fontFamily: tokens.font.heading,
                fontSize: '22px',
                fontWeight: 600,
                color: tokens.text.primary,
                margin: 0,
                letterSpacing: '-0.01em',
                lineHeight: 1.2,
              }}
            >
              {channel.name}
            </h1>

            {/* Status badge */}
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '2px 10px',
                borderRadius: '4px',
                backgroundColor: `${statusColor}14`,
                border: `1px solid ${statusColor}30`,
                fontFamily: tokens.font.mono,
                fontSize: '11px',
                fontWeight: 500,
                color: statusColor,
                letterSpacing: '0.03em',
                textTransform: 'uppercase' as const,
                lineHeight: '18px',
              }}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: statusColor,
                }}
                aria-hidden="true"
              />
              {statusLabel}
            </span>
          </div>
        </div>

        {/* Right: Date range */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            borderRadius: '6px',
            backgroundColor: tokens.bg.nested,
            border: `1px solid ${tokens.border.subtle}`,
          }}
        >
          {/* Calendar icon */}
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
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            {dateRange.label}
          </span>
        </div>
      </div>
    </>
  );
};

export default ChannelHeader;
