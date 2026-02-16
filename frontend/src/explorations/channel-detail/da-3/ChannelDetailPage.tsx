/**
 * DA-3 TIMELINE — Channel Detail Page
 *
 * Temporal narrative ribbon layout: time is the primary organizing spine.
 * All 4 states handled: loading, empty, error, ready.
 *
 * Ready layout (top to bottom):
 *   1. ChannelHeader (compact info bar)
 *   2. PerformanceMetrics (horizontal strip of 4 metrics)
 *   3. TrendSection (HERO — full-width timeline ribbon with confidence river)
 *   4. Two panels side by side:
 *      - Left: VerificationSection
 *      - Right: ConfidenceSection
 *   5. SignatureSVG (attribution flow river)
 *
 * Google Fonts imported inline for Syne, IBM Plex Sans, IBM Plex Mono.
 * All colors from token palette. No Tailwind.
 */

import React from 'react';
import type { ChannelDetailState, ChannelDetailData } from '../shared/types';
import { CHANNEL_COLORS } from '../shared/types';
import { ChannelHeader } from './components/ChannelHeader';
import { PerformanceMetrics } from './components/PerformanceMetrics';
import { TrendSection } from './components/TrendSection';
import { VerificationSection } from './components/VerificationSection';
import { ConfidenceSection } from './components/ConfidenceSection';
import { SignatureSVG } from './components/SignatureSVG';

/* -- Design Tokens -------------------------------------------------------- */
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
  },
} as const;

/* -- Skeleton keyframes --------------------------------------------------- */
const skeletonKeyframes = `
@keyframes da3-skeleton-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}
@media (prefers-reduced-motion: reduce) {
  .da3-skeleton-bar {
    animation: none !important;
    opacity: 0.5;
  }
}
`;

/* -- Loading State -------------------------------------------------------- */
const LoadingState: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
    <style>{skeletonKeyframes}</style>

    {/* Header skeleton */}
    <div
      style={{
        height: '56px',
        borderRadius: '8px',
        background: tokens.bg.card,
        border: `1px solid ${tokens.border.subtle}`,
      }}
    >
      <div
        className="da3-skeleton-bar"
        style={{
          width: '220px',
          height: '16px',
          margin: '20px 24px',
          borderRadius: '4px',
          background: `linear-gradient(90deg, ${tokens.bg.nested}, ${tokens.bg.elevated}, ${tokens.bg.nested})`,
          animation: 'da3-skeleton-pulse 2s ease-in-out infinite',
        }}
      />
    </div>

    {/* Metrics skeleton */}
    <div
      style={{
        display: 'flex',
        gap: '1px',
        height: '88px',
        borderRadius: '8px',
        background: tokens.bg.card,
        border: `1px solid ${tokens.border.subtle}`,
        overflow: 'hidden',
      }}
    >
      {[0, 1, 2, 3].map((i) => (
        <div key={i} style={{ flex: '1 1 0', padding: '16px 20px' }}>
          <div
            className="da3-skeleton-bar"
            style={{
              width: '60px',
              height: '8px',
              borderRadius: '4px',
              background: `linear-gradient(90deg, ${tokens.bg.nested}, ${tokens.bg.elevated}, ${tokens.bg.nested})`,
              animation: `da3-skeleton-pulse 2s ease-in-out infinite ${i * 0.15}s`,
              marginBottom: '12px',
            }}
          />
          <div
            className="da3-skeleton-bar"
            style={{
              width: '90px',
              height: '20px',
              borderRadius: '4px',
              background: `linear-gradient(90deg, ${tokens.bg.nested}, ${tokens.bg.elevated}, ${tokens.bg.nested})`,
              animation: `da3-skeleton-pulse 2s ease-in-out infinite ${i * 0.15 + 0.1}s`,
            }}
          />
        </div>
      ))}
    </div>

    {/* Timeline ribbon skeleton (hero placeholder) */}
    <div
      style={{
        height: '360px',
        borderRadius: '8px',
        background: tokens.bg.card,
        border: `1px solid ${tokens.border.subtle}`,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Topographic timeline band placeholder */}
      <div
        className="da3-skeleton-bar"
        style={{
          position: 'absolute',
          left: '24px',
          right: '24px',
          top: '50%',
          transform: 'translateY(-50%)',
          height: '80px',
          borderRadius: '40px',
          background: `linear-gradient(90deg, ${tokens.bg.nested}00 0%, ${tokens.bg.nested} 20%, ${tokens.bg.elevated}60 50%, ${tokens.bg.nested} 80%, ${tokens.bg.nested}00 100%)`,
          animation: 'da3-skeleton-pulse 2.5s ease-in-out infinite',
        }}
      />
      {/* Faint timeline ticks */}
      <div style={{ position: 'absolute', bottom: '24px', left: '24px', right: '24px', display: 'flex', justifyContent: 'space-between' }}>
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="da3-skeleton-bar"
            style={{
              width: '36px',
              height: '8px',
              borderRadius: '4px',
              background: tokens.bg.nested,
              animation: `da3-skeleton-pulse 2s ease-in-out infinite ${i * 0.2}s`,
            }}
          />
        ))}
      </div>
    </div>

    {/* Two panel skeleton */}
    <div style={{ display: 'flex', gap: '16px' }}>
      {[0, 1].map((i) => (
        <div
          key={i}
          style={{
            flex: '1 1 0',
            height: '200px',
            borderRadius: '8px',
            background: tokens.bg.card,
            border: `1px solid ${tokens.border.subtle}`,
            padding: '24px',
          }}
        >
          <div
            className="da3-skeleton-bar"
            style={{
              width: '120px',
              height: '12px',
              borderRadius: '4px',
              background: `linear-gradient(90deg, ${tokens.bg.nested}, ${tokens.bg.elevated}, ${tokens.bg.nested})`,
              animation: `da3-skeleton-pulse 2s ease-in-out infinite ${i * 0.3}s`,
            }}
          />
        </div>
      ))}
    </div>
  </div>
);

/* -- Empty State ---------------------------------------------------------- */
const EMPTY_CONTENT: Record<string, { icon: React.ReactNode; heading: string; body: string }> = {
  'no-data-yet': {
    icon: (
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke={tokens.text.muted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
    heading: 'No attribution data yet',
    body: 'Connect your first platform to begin attribution modeling.',
  },
  'building-model': {
    icon: (
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke={tokens.confidence.medium} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
    heading: 'Building your attribution model',
    body: '', // Dynamically set with currentDay
  },
  'no-results-filter': {
    icon: (
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke={tokens.text.muted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
      </svg>
    ),
    heading: 'No results for these filters',
    body: 'Adjust your date range or filters to see attribution data.',
  },
  'feature-locked': {
    icon: (
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke={tokens.text.muted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
    ),
    heading: 'Channel detail requires a Pro plan',
    body: 'Upgrade to access detailed channel attribution and verification data.',
  },
};

interface EmptyStateProps {
  variant: string;
  currentDay?: number;
}

const EmptyState: React.FC<EmptyStateProps> = ({ variant, currentDay }) => {
  const content = EMPTY_CONTENT[variant] || EMPTY_CONTENT['no-data-yet'];
  const body = variant === 'building-model' && currentDay != null
    ? `Day ${currentDay} of 14 \u2014 accumulating evidence for your first model.`
    : content.body;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '400px',
        gap: '20px',
        padding: '48px 24px',
      }}
    >
      <div
        style={{
          width: '80px',
          height: '80px',
          borderRadius: '50%',
          background: tokens.bg.card,
          border: `1px solid ${tokens.border.subtle}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {content.icon}
      </div>

      <h2
        style={{
          fontFamily: tokens.font.heading,
          fontSize: '20px',
          fontWeight: 600,
          color: tokens.text.primary,
          margin: 0,
          textAlign: 'center',
        }}
      >
        {content.heading}
      </h2>

      <p
        style={{
          fontFamily: tokens.font.body,
          fontSize: '14px',
          color: tokens.text.secondary,
          margin: 0,
          textAlign: 'center',
          maxWidth: '400px',
          lineHeight: 1.6,
        }}
      >
        {body}
      </p>

      {variant === 'building-model' && currentDay != null && (
        <div
          style={{
            width: '200px',
            height: '4px',
            borderRadius: '2px',
            background: tokens.bg.nested,
            overflow: 'hidden',
            marginTop: '4px',
          }}
        >
          <div
            style={{
              width: `${(currentDay / 14) * 100}%`,
              height: '100%',
              borderRadius: '2px',
              background: `linear-gradient(90deg, ${tokens.confidence.medium}, ${tokens.confidence.high})`,
              transition: `width ${tokens.motion.medium} ease`,
            }}
          />
        </div>
      )}
    </div>
  );
};

/* -- Error State ---------------------------------------------------------- */
interface ErrorStateProps {
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
  onRetry?: () => void;
}

const ErrorState: React.FC<ErrorStateProps> = ({ error, onRetry }) => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '400px',
      gap: '20px',
      padding: '48px 24px',
    }}
  >
    <div
      style={{
        width: '80px',
        height: '80px',
        borderRadius: '50%',
        background: `${tokens.confidence.low}0A`,
        border: `1px solid ${tokens.confidence.low}20`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <svg
        width="36"
        height="36"
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
        fontSize: '20px',
        fontWeight: 600,
        color: tokens.text.primary,
        margin: 0,
        textAlign: 'center',
      }}
    >
      {error.title}
    </h2>

    <p
      style={{
        fontFamily: tokens.font.body,
        fontSize: '14px',
        color: tokens.text.secondary,
        margin: 0,
        textAlign: 'center',
        maxWidth: '420px',
        lineHeight: 1.6,
      }}
    >
      {error.message}
    </p>

    <span
      style={{
        fontFamily: tokens.font.mono,
        fontSize: '11px',
        color: tokens.text.muted,
        padding: '4px 10px',
        background: tokens.bg.nested,
        borderRadius: '4px',
      }}
    >
      {error.correlationId}
    </span>

    <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
      {error.retryable && (
        <button
          type="button"
          onClick={onRetry}
          style={{
            fontFamily: tokens.font.body,
            fontSize: '13px',
            fontWeight: 500,
            color: '#FFFFFF',
            background: tokens.brand,
            border: 'none',
            borderRadius: '6px',
            padding: '8px 20px',
            cursor: 'pointer',
            transition: `opacity ${tokens.motion.short} ease`,
          }}
        >
          Retry
        </button>
      )}

      {error.action && (
        <button
          type="button"
          onClick={error.action.onClick}
          style={{
            fontFamily: tokens.font.body,
            fontSize: '13px',
            fontWeight: 500,
            color: tokens.text.secondary,
            background: 'transparent',
            border: `1px solid ${tokens.border.default}`,
            borderRadius: '6px',
            padding: '8px 20px',
            cursor: 'pointer',
            transition: `all ${tokens.motion.short} ease`,
          }}
        >
          {error.action.label}
        </button>
      )}
    </div>
  </div>
);

/* -- Ready State ---------------------------------------------------------- */
const ReadyState: React.FC<{ data: ChannelDetailData }> = ({ data }) => {
  const channelColor = CHANNEL_COLORS[data.channel.platform] || CHANNEL_COLORS['other'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* 1. Channel Header (compact) */}
      <ChannelHeader
        channel={data.channel}
        dateRange={data.dateRange}
        modelInfo={data.modelInfo}
      />

      {/* 2. Performance Metrics (horizontal strip) */}
      <PerformanceMetrics
        performance={data.performance}
        confidenceLevel={data.confidenceRange.level}
      />

      {/* 3. HERO: TrendSection (full-width timeline ribbon) */}
      <TrendSection
        trendData={data.trendData}
        channelColor={channelColor}
        confidenceLevel={data.confidenceRange.level}
      />

      {/* 4. Two panels side by side */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '16px',
        }}
      >
        {/* Left: Verification */}
        <VerificationSection
          verification={data.verification}
          channelName={data.channel.name}
        />

        {/* Right: Confidence */}
        <ConfidenceSection
          confidenceRange={data.confidenceRange}
        />
      </div>

      {/* 5. SignatureSVG (attribution flow river) */}
      <SignatureSVG
        channelName={data.channel.name}
        channelColor={channelColor}
        verifiedRevenueFormatted={data.verification.verifiedFormatted}
      />
    </div>
  );
};

/* -- Page Component ------------------------------------------------------- */

interface ChannelDetailPageProps {
  state: ChannelDetailState;
}

export const ChannelDetailPage: React.FC<ChannelDetailPageProps> = ({ state }) => {
  return (
    <main
      style={{
        background: tokens.bg.page,
        minHeight: 'calc(100vh - 56px)',
        padding: '24px',
        maxWidth: '1200px',
        margin: '0 auto',
      }}
    >
      {/* Google Fonts import */}
      <style>{'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}</style>

      {state.status === 'loading' && <LoadingState />}

      {state.status === 'empty' && (
        <EmptyState
          variant={state.emptyVariant}
          currentDay={state.currentDay}
        />
      )}

      {state.status === 'error' && (
        <ErrorState error={state.error} />
      )}

      {state.status === 'ready' && (
        <ReadyState data={state.data} />
      )}
    </main>
  );
};

export default ChannelDetailPage;
