/**
 * DA-1 COCKPIT — Channel Detail Page
 *
 * Main page with cockpit grid layout. Handles all 4 states:
 *   - loading: Skeleton screens with shimmer animation
 *   - empty: Context-specific messages per variant
 *   - error: Shows title, message, correlationId, retry button
 *   - ready: Multi-panel cockpit grid with all instrument sections
 *
 * Layout: Aerospace-inspired multi-panel grid.
 * All values pre-formatted from ChannelDetailData.
 */

import React, { useEffect, useId } from 'react';
import type { ChannelDetailState, ChannelDetailData, ConfidenceLevel } from '../shared/types';
import { CHANNEL_COLORS } from '../shared/types';
import { ChannelHeader } from './components/ChannelHeader';
import { PerformanceMetrics } from './components/PerformanceMetrics';
import { ConfidenceSection } from './components/ConfidenceSection';
import { VerificationSection } from './components/VerificationSection';
import { TrendSection } from './components/TrendSection';
import { SignatureSVG } from './components/SignatureSVG';

/* ── Design Tokens ──────────────────────────────────────────────── */
const tokens = {
  bg: {
    page: '#0A0E1A',
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
    micro: '120ms',
    short: '200ms',
    medium: '300ms',
    breathe: '3000ms',
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
} as const;

/* ── Keyframes ─────────────────────────────────────────────────── */

const KEYFRAMES_ID = 'da1-page-keyframes';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(KEYFRAMES_ID)) return;

  const style = document.createElement('style');
  style.id = KEYFRAMES_ID;
  style.textContent = `
    @keyframes da1Shimmer {
      0% { background-position: -400px 0; }
      100% { background-position: 400px 0; }
    }
    @keyframes da1FadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @media (prefers-reduced-motion: reduce) {
      .da1-skeleton, .da1-page-content {
        animation: none !important;
      }
      .da1-skeleton {
        background: ${tokens.bg.nested} !important;
      }
    }
  `;
  document.head.appendChild(style);
}

/* ── Skeleton Components ───────────────────────────────────────── */

const SkeletonBlock: React.FC<{ width?: string; height: string; borderRadius?: string }> = ({
  width = '100%',
  height,
  borderRadius = '8px',
}) => (
  <div
    className="da1-skeleton"
    style={{
      width,
      height,
      borderRadius,
      background: `linear-gradient(90deg, ${tokens.bg.nested} 0%, ${tokens.bg.elevated} 50%, ${tokens.bg.nested} 100%)`,
      backgroundSize: '800px 100%',
      animation: 'da1Shimmer 1.5s ease-in-out infinite',
    }}
  />
);

const LoadingState: React.FC = () => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      padding: '24px',
      maxWidth: '1280px',
      margin: '0 auto',
      width: '100%',
      boxSizing: 'border-box',
    }}
    role="status"
    aria-label="Loading channel detail data"
  >
    {/* Header skeleton */}
    <SkeletonBlock height="72px" />

    {/* Metrics row skeleton */}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
      <SkeletonBlock height="120px" />
      <SkeletonBlock height="120px" />
      <SkeletonBlock height="120px" />
      <SkeletonBlock height="120px" />
    </div>

    {/* Two-column skeleton */}
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
      <SkeletonBlock height="320px" />
      <SkeletonBlock height="320px" />
    </div>

    {/* Trend chart skeleton */}
    <SkeletonBlock height="360px" />

    {/* Heartbeat skeleton */}
    <SkeletonBlock height="140px" />

    {/* Responsive overrides for loading */}
    <style>{`
      @media (max-width: 1024px) {
        [role="status"] > div:nth-child(2) {
          grid-template-columns: repeat(2, 1fr) !important;
        }
        [role="status"] > div:nth-child(3) {
          grid-template-columns: 1fr !important;
        }
      }
      @media (max-width: 600px) {
        [role="status"] > div:nth-child(2) {
          grid-template-columns: 1fr !important;
        }
      }
    `}</style>
  </div>
);

/* ── Empty State ───────────────────────────────────────────────── */

interface EmptyStateProps {
  variant: 'no-data-yet' | 'building-model' | 'no-results-filter' | 'feature-locked';
  currentDay?: number;
}

const EMPTY_CONTENT: Record<string, { icon: string; title: string; message: string }> = {
  'no-data-yet': {
    icon: 'connect',
    title: 'No channel data available',
    message: 'Connect your first platform to begin attribution modeling.',
  },
  'building-model': {
    icon: 'building',
    title: 'Building your attribution model',
    message: '', // dynamically set with currentDay
  },
  'no-results-filter': {
    icon: 'filter',
    title: 'No results match current filters',
    message: 'Adjust the date range or channel filters to view attribution data.',
  },
  'feature-locked': {
    icon: 'lock',
    title: 'This feature requires a plan upgrade',
    message: 'Channel-level attribution detail is available on Pro and Enterprise plans.',
  },
};

const EmptyIcon: React.FC<{ type: string; color: string }> = ({ type, color }) => {
  const commonProps = {
    width: 48,
    height: 48,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: color,
    strokeWidth: 1.5,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true as const,
  };

  switch (type) {
    case 'connect':
      return (
        <svg {...commonProps}>
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
      );
    case 'building':
      return (
        <svg {...commonProps}>
          <path d="M12 2v4" />
          <path d="m6.343 6.343 2.828 2.828" />
          <path d="M2 12h4" />
          <path d="m6.343 17.657 2.828-2.828" />
          <path d="M12 18v4" />
          <path d="m17.657 17.657-2.828-2.828" />
          <path d="M22 12h-4" />
          <path d="m17.657 6.343-2.828 2.828" />
        </svg>
      );
    case 'filter':
      return (
        <svg {...commonProps}>
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
        </svg>
      );
    case 'lock':
      return (
        <svg {...commonProps}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      );
    default:
      return null;
  }
};

const EmptyState: React.FC<EmptyStateProps> = ({ variant, currentDay }) => {
  const content = EMPTY_CONTENT[variant];
  if (!content) return null;

  const message = variant === 'building-model'
    ? `Day ${currentDay || 1} of 14 \u2014 accumulating evidence for your first model.`
    : content.message;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '20px',
        padding: '80px 24px',
        maxWidth: '520px',
        margin: '0 auto',
        textAlign: 'center',
      }}
      role="status"
    >
      <div
        style={{
          width: '80px',
          height: '80px',
          borderRadius: '16px',
          background: tokens.bg.card,
          border: `1px solid ${tokens.border.subtle}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <EmptyIcon type={content.icon} color={tokens.text.muted} />
      </div>

      <h2
        style={{
          fontFamily: tokens.font.heading,
          fontSize: '24px',
          fontWeight: 600,
          color: tokens.text.primary,
          margin: 0,
          lineHeight: 1.3,
        }}
      >
        {content.title}
      </h2>

      <p
        style={{
          fontFamily: tokens.font.body,
          fontSize: '16px',
          color: tokens.text.secondary,
          margin: 0,
          lineHeight: 1.6,
        }}
      >
        {message}
      </p>

      {variant === 'building-model' && currentDay !== undefined && (
        <div
          style={{
            width: '100%',
            maxWidth: '280px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div
            style={{
              height: '6px',
              borderRadius: '3px',
              background: tokens.bg.nested,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${(currentDay / 14) * 100}%`,
                borderRadius: '3px',
                background: `linear-gradient(90deg, ${tokens.brand}, ${tokens.confidence.high})`,
                transition: `width ${tokens.motion.medium} ${tokens.motion.easing}`,
              }}
            />
          </div>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              color: tokens.text.muted,
            }}
          >
            {currentDay}/14 days
          </span>
        </div>
      )}
    </div>
  );
};

/* ── Error State ───────────────────────────────────────────────── */

interface ErrorStateInnerProps {
  error: {
    title: string;
    message: string;
    correlationId: string;
    retryable: boolean;
    action?: {
      label: string;
      onClick: () => void;
    };
  };
}

const ErrorState: React.FC<ErrorStateInnerProps> = ({ error }) => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '24px',
      padding: '80px 24px',
      maxWidth: '520px',
      margin: '0 auto',
      textAlign: 'center',
    }}
    role="alert"
  >
    {/* Error icon */}
    <div
      style={{
        width: '80px',
        height: '80px',
        borderRadius: '16px',
        background: `${tokens.confidence.low}10`,
        border: `1px solid ${tokens.confidence.low}30`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <svg
        width="40"
        height="40"
        viewBox="0 0 24 24"
        fill="none"
        stroke={tokens.confidence.low}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    </div>

    <h2
      style={{
        fontFamily: tokens.font.heading,
        fontSize: '24px',
        fontWeight: 600,
        color: tokens.text.primary,
        margin: 0,
        lineHeight: 1.3,
      }}
    >
      {error.title}
    </h2>

    <p
      style={{
        fontFamily: tokens.font.body,
        fontSize: '16px',
        color: tokens.text.secondary,
        margin: 0,
        lineHeight: 1.6,
      }}
    >
      {error.message}
    </p>

    {/* Correlation ID */}
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 16px',
        background: tokens.bg.card,
        borderRadius: '6px',
        border: `1px solid ${tokens.border.subtle}`,
      }}
    >
      <span
        style={{
          fontFamily: tokens.font.body,
          fontSize: '12px',
          color: tokens.text.muted,
        }}
      >
        Correlation ID
      </span>
      <span
        style={{
          fontFamily: tokens.font.mono,
          fontSize: '12px',
          color: tokens.text.secondary,
          fontWeight: 500,
        }}
      >
        {error.correlationId}
      </span>
    </div>

    {/* Action buttons */}
    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
      {error.retryable && (
        <button
          onClick={() => window.location.reload()}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 24px',
            borderRadius: '8px',
            border: 'none',
            background: tokens.brand,
            color: '#FFFFFF',
            fontFamily: tokens.font.body,
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: `all ${tokens.motion.short} ${tokens.motion.easing}`,
          }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M21 2v6h-6" />
            <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
            <path d="M3 22v-6h6" />
            <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
          </svg>
          Retry
        </button>
      )}

      {error.action && (
        <button
          onClick={error.action.onClick}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 24px',
            borderRadius: '8px',
            border: `1px solid ${tokens.border.default}`,
            background: 'transparent',
            color: tokens.text.secondary,
            fontFamily: tokens.font.body,
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
            transition: `all ${tokens.motion.short} ${tokens.motion.easing}`,
          }}
        >
          {error.action.label}
        </button>
      )}
    </div>
  </div>
);

/* ── Ready State: Cockpit Grid ─────────────────────────────────── */

const ReadyState: React.FC<{ data: ChannelDetailData }> = ({ data }) => {
  const layoutId = useId();
  const channelColor = CHANNEL_COLORS[data.channel.platform] || CHANNEL_COLORS['other'];
  const confidenceLevel: ConfidenceLevel = data.confidenceRange.level;

  return (
    <div
      className="da1-page-content"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        padding: '24px',
        maxWidth: '1280px',
        margin: '0 auto',
        width: '100%',
        boxSizing: 'border-box',
        animation: 'da1FadeIn 300ms ease-out',
      }}
    >
      {/* Row 1: Channel Header (full width) */}
      <ChannelHeader
        channel={data.channel}
        dateRange={data.dateRange}
        modelInfo={data.modelInfo}
      />

      {/* Row 2: Performance Metrics (4-column instrument gauges) */}
      <PerformanceMetrics
        performance={data.performance}
        confidenceLevel={confidenceLevel}
      />

      {/* Row 3: Two-panel cockpit — Confidence + Verification */}
      <div
        id={layoutId}
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '16px',
        }}
      >
        <ConfidenceSection
          confidenceRange={data.confidenceRange}
        />
        <VerificationSection
          verification={data.verification}
        />
      </div>

      {/* Row 4: Trend Chart (full width) */}
      <TrendSection
        trendData={data.trendData}
        channelColor={channelColor}
        confidenceLevel={confidenceLevel}
      />

      {/* Row 5: Signature SVG — Channel Sync Heartbeat */}
      <SignatureSVG
        confidenceLevel={confidenceLevel}
        lastUpdatedFormatted={data.modelInfo.lastUpdatedFormatted}
        channelColor={channelColor}
      />

      {/* Responsive overrides */}
      <style>{`
        @media (max-width: 1024px) {
          #${CSS.escape(layoutId)} {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
};

/* ── Props ──────────────────────────────────────────────────────── */

interface ChannelDetailPageProps {
  state: ChannelDetailState;
}

/* ── Main Component ────────────────────────────────────────────── */

export const ChannelDetailPage: React.FC<ChannelDetailPageProps> = ({ state }) => {
  useEffect(() => {
    ensureKeyframes();
  }, []);

  return (
    <main
      style={{
        minHeight: 'calc(100vh - 56px)',
        background: tokens.bg.page,
        fontFamily: tokens.font.body,
      }}
    >
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>

      {state.status === 'loading' && <LoadingState />}

      {state.status === 'empty' && (
        <EmptyState
          variant={state.emptyVariant}
          currentDay={state.currentDay}
        />
      )}

      {state.status === 'error' && <ErrorState error={state.error} />}

      {state.status === 'ready' && <ReadyState data={state.data} />}
    </main>
  );
};

export default ChannelDetailPage;
