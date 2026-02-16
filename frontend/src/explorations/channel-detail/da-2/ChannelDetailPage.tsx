/**
 * DA-2 DOSSIER -- Channel Detail Page
 *
 * Intelligence dossier layout: vertical scrolling document with numbered sections.
 * Handles all 4 states: loading, empty (4 variants), error, ready.
 * Each section flows like a classified briefing with thin dividers.
 */
import React, { useEffect } from 'react';
import type { ChannelDetailState, ChannelDetailData, ConfidenceLevel } from '../shared/types';
import { CHANNEL_COLORS } from '../shared/types';
import ChannelHeader from './components/ChannelHeader';
import PerformanceMetrics from './components/PerformanceMetrics';
import VerificationSection from './components/VerificationSection';
import ConfidenceSection from './components/ConfidenceSection';
import SignatureSVG from './components/SignatureSVG';
import TrendSection from './components/TrendSection';

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

/* ── Reduced motion style injection ──────────────────────── */
const MOTION_STYLE_ID = 'da2-reduced-motion';
function ensureMotionStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(MOTION_STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = MOTION_STYLE_ID;
  style.textContent = `
    @media (prefers-reduced-motion: reduce) {
      .da2-skeleton-pulse {
        animation: none !important;
        opacity: 0.3 !important;
      }
    }
    @keyframes da2-skeleton-pulse {
      0%, 100% { opacity: 0.15; }
      50% { opacity: 0.35; }
    }
    .da2-skeleton-pulse {
      animation: da2-skeleton-pulse 2000ms cubic-bezier(0.4, 0, 0.2, 1) infinite;
    }
  `;
  document.head.appendChild(style);
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

/* ── Page wrapper styles ─────────────────────────────────── */
const pageStyles = {
  wrapper: {
    background: COLORS.pageBg,
    minHeight: 'calc(100vh - 57px)',
    padding: '0 24px 64px',
  } as React.CSSProperties,
  document: {
    maxWidth: 840,
    margin: '0 auto',
  } as React.CSSProperties,
  classifiedStamp: {
    fontFamily: FONT.mono,
    fontSize: 10,
    fontWeight: 600,
    color: COLORS.text.muted,
    letterSpacing: 3,
    textTransform: 'uppercase' as const,
    textAlign: 'center' as const,
    padding: '24px 0 8px',
    borderBottom: `1px solid ${COLORS.border.subtle}`,
    marginBottom: 0,
  } as React.CSSProperties,
  modelInfo: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 16,
    padding: '12px 0',
    borderBottom: `1px solid ${COLORS.border.subtle}`,
    flexWrap: 'wrap' as const,
  } as React.CSSProperties,
  modelInfoItem: {
    fontFamily: FONT.mono,
    fontSize: 11,
    fontWeight: 500,
    color: COLORS.text.muted,
    letterSpacing: 0.5,
  } as React.CSSProperties,
  modelInfoValue: {
    color: COLORS.text.secondary,
  } as React.CSSProperties,
  signatureSvgWrapper: {
    padding: '20px 0 0',
    display: 'flex',
    justifyContent: 'center',
  } as React.CSSProperties,
} as const;

/* ── Loading Skeleton ────────────────────────────────────── */
const skeletonBlock = (width: string | number, height: number, marginBottom = 12): React.CSSProperties => ({
  background: COLORS.nestedBg,
  borderRadius: 4,
  width,
  height,
  marginBottom,
});

const LoadingSkeleton: React.FC = () => (
  <div style={pageStyles.document} role="status" aria-label="Loading channel data">
    {/* Classified stamp skeleton */}
    <div style={{ padding: '24px 0 16px', textAlign: 'center' as const, borderBottom: `1px solid ${COLORS.border.subtle}` }}>
      <div className="da2-skeleton-pulse" style={{ ...skeletonBlock(180, 12, 0), margin: '0 auto' }} />
    </div>

    {/* Section 01: Header skeleton */}
    <div style={{ padding: '32px 0 24px', borderBottom: `1px solid ${COLORS.border.subtle}` }}>
      <div className="da2-skeleton-pulse" style={skeletonBlock(120, 10)} />
      <div className="da2-skeleton-pulse" style={skeletonBlock(280, 24, 16)} />
      <div style={{ display: 'flex', gap: 12 }}>
        <div className="da2-skeleton-pulse" style={skeletonBlock(80, 28, 0)} />
        <div className="da2-skeleton-pulse" style={skeletonBlock(80, 28, 0)} />
        <div className="da2-skeleton-pulse" style={skeletonBlock(140, 28, 0)} />
      </div>
    </div>

    {/* Section 02: Metrics skeleton */}
    <div style={{ padding: '32px 0 24px', borderBottom: `1px solid ${COLORS.border.subtle}` }}>
      <div className="da2-skeleton-pulse" style={skeletonBlock(160, 10, 20)} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="da2-skeleton-pulse"
            style={{
              background: COLORS.nestedBg,
              borderRadius: 6,
              padding: '20px 24px',
              height: 120,
            }}
          />
        ))}
      </div>
    </div>

    {/* Section 03: Verification skeleton */}
    <div style={{ padding: '32px 0 24px', borderBottom: `1px solid ${COLORS.border.subtle}` }}>
      <div className="da2-skeleton-pulse" style={skeletonBlock(180, 10, 20)} />
      <div className="da2-skeleton-pulse" style={skeletonBlock('100%', 160, 12)} />
      <div className="da2-skeleton-pulse" style={skeletonBlock('100%', 40, 0)} />
    </div>

    {/* Section 04: Confidence skeleton */}
    <div style={{ padding: '32px 0 24px', borderBottom: `1px solid ${COLORS.border.subtle}` }}>
      <div className="da2-skeleton-pulse" style={skeletonBlock(150, 10, 20)} />
      <div className="da2-skeleton-pulse" style={skeletonBlock(200, 36, 12)} />
      <div className="da2-skeleton-pulse" style={skeletonBlock(320, 14, 16)} />
      <div className="da2-skeleton-pulse" style={skeletonBlock('100%', 80, 0)} />
    </div>

    {/* Section 05: Chart skeleton */}
    <div style={{ padding: '32px 0 24px' }}>
      <div className="da2-skeleton-pulse" style={skeletonBlock(190, 10, 20)} />
      <div className="da2-skeleton-pulse" style={skeletonBlock('100%', 280, 0)} />
    </div>

    {/* Screen-reader loading announcement */}
    <span style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0,0,0,0)' }}>
      Loading channel detail data...
    </span>
  </div>
);

/* ── Empty States ────────────────────────────────────────── */
interface EmptyConfig {
  title: string;
  message: string;
  icon: string;
}

const EMPTY_CONFIGS: Record<string, EmptyConfig | ((day?: number) => EmptyConfig)> = {
  'no-data-yet': {
    title: 'No Channel Data Available',
    message: 'Connect your first platform to begin attribution modeling.',
    icon: 'link',
  },
  'building-model': (day?: number) => ({
    title: 'Model Calibration In Progress',
    message: `Day ${day ?? 1} of 14 \u2014 accumulating evidence for your first model.`,
    icon: 'clock',
  }),
  'no-results-filter': {
    title: 'No Matching Channels',
    message: 'No channels match this filter.',
    icon: 'filter',
  },
  'feature-locked': {
    title: 'Feature Unavailable',
    message: 'Available on Agency plan.',
    icon: 'lock',
  },
};

const emptyStyles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 24px',
    textAlign: 'center' as const,
    minHeight: 400,
  } as React.CSSProperties,
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: '50%',
    background: COLORS.nestedBg,
    border: `1px solid ${COLORS.border.default}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  } as React.CSSProperties,
  title: {
    fontFamily: FONT.heading,
    fontSize: 18,
    fontWeight: 600,
    color: COLORS.text.primary,
    margin: '0 0 12px',
    lineHeight: 1.3,
  } as React.CSSProperties,
  message: {
    fontFamily: FONT.body,
    fontSize: 14,
    fontWeight: 400,
    color: COLORS.text.secondary,
    margin: 0,
    maxWidth: 400,
    lineHeight: 1.6,
  } as React.CSSProperties,
};

const EmptyIconSVG: Record<string, React.ReactNode> = {
  link: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={COLORS.text.muted} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  ),
  clock: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={COLORS.text.muted} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  filter: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={COLORS.text.muted} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  ),
  lock: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={COLORS.text.muted} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  ),
};

const EmptyState: React.FC<{ variant: string; currentDay?: number }> = ({ variant, currentDay }) => {
  const configEntry = EMPTY_CONFIGS[variant];
  const config = typeof configEntry === 'function' ? configEntry(currentDay) : configEntry;

  if (!config) return null;

  return (
    <div style={pageStyles.document}>
      <div style={emptyStyles.container} role="status">
        <div style={emptyStyles.iconCircle}>
          {EmptyIconSVG[config.icon] ?? null}
        </div>
        <h2 style={emptyStyles.title}>{config.title}</h2>
        <p style={emptyStyles.message}>{config.message}</p>
      </div>
    </div>
  );
};

/* ── Error State ─────────────────────────────────────────── */
const errorStyles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    padding: '80px 24px',
    textAlign: 'center' as const,
    minHeight: 400,
  } as React.CSSProperties,
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: '50%',
    background: `${COLORS.confidence.low}14`,
    border: `1px solid ${COLORS.confidence.low}33`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  } as React.CSSProperties,
  title: {
    fontFamily: FONT.heading,
    fontSize: 18,
    fontWeight: 600,
    color: COLORS.text.primary,
    margin: '0 0 12px',
    lineHeight: 1.3,
  } as React.CSSProperties,
  message: {
    fontFamily: FONT.body,
    fontSize: 14,
    fontWeight: 400,
    color: COLORS.text.secondary,
    margin: '0 0 16px',
    maxWidth: 480,
    lineHeight: 1.6,
  } as React.CSSProperties,
  correlationId: {
    fontFamily: FONT.mono,
    fontSize: 11,
    fontWeight: 500,
    color: COLORS.text.muted,
    margin: '0 0 20px',
    letterSpacing: 0.5,
  } as React.CSSProperties,
  retryButton: {
    fontFamily: FONT.body,
    fontSize: 14,
    fontWeight: 600,
    color: COLORS.text.primary,
    background: COLORS.brand,
    border: 'none',
    borderRadius: 6,
    padding: '10px 24px',
    cursor: 'pointer',
    marginBottom: 12,
    transition: 'opacity 200ms ease',
  } as React.CSSProperties,
  actionLink: {
    fontFamily: FONT.body,
    fontSize: 13,
    fontWeight: 500,
    color: COLORS.brand,
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    textDecoration: 'underline',
    padding: 4,
  } as React.CSSProperties,
};

const ErrorState: React.FC<{ error: NonNullable<Extract<ChannelDetailState, { status: 'error' }>['error']> }> = ({ error }) => (
  <div style={pageStyles.document}>
    <div style={errorStyles.container} role="alert">
      <div style={errorStyles.iconCircle}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={COLORS.confidence.low} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h2 style={errorStyles.title}>{error.title}</h2>
      <p style={errorStyles.message}>{error.message}</p>
      <p style={errorStyles.correlationId}>Error ID: {error.correlationId}</p>
      {error.retryable && (
        <button
          style={errorStyles.retryButton}
          onClick={() => window.location.reload()}
          type="button"
        >
          Retry
        </button>
      )}
      {error.action && (
        <button
          style={errorStyles.actionLink}
          onClick={error.action.onClick}
          type="button"
        >
          {error.action.label}
        </button>
      )}
    </div>
  </div>
);

/* ── Ready State ─────────────────────────────────────────── */
const ReadyState: React.FC<{ data: ChannelDetailData }> = ({ data }) => {
  const channelColor = CHANNEL_COLORS[data.channel.platform] ?? CHANNEL_COLORS.other;

  return (
    <div style={pageStyles.document}>
      {/* Classified stamp */}
      <p style={pageStyles.classifiedStamp}>
        Channel Intelligence Dossier
      </p>

      {/* Model info bar */}
      <div style={pageStyles.modelInfo}>
        <span style={pageStyles.modelInfoItem}>
          Model v<span style={pageStyles.modelInfoValue}>{data.modelInfo.version}</span>
        </span>
        <span style={pageStyles.modelInfoItem}>
          Updated <span style={pageStyles.modelInfoValue}>{data.modelInfo.lastUpdatedFormatted}</span>
        </span>
        <span style={pageStyles.modelInfoItem}>
          Next update <span style={pageStyles.modelInfoValue}>{data.modelInfo.nextUpdate}</span>
        </span>
      </div>

      {/* Section 01: Channel Brief */}
      <ChannelHeader channel={data.channel} dateRange={data.dateRange} />

      {/* Section 02: Performance Summary */}
      <PerformanceMetrics
        performance={data.performance}
        verification={data.verification}
      />

      {/* Section 03: Revenue Verification */}
      <VerificationSection
        verification={data.verification}
        channelName={data.channel.name}
      />

      {/* Section 04: Model Confidence */}
      <ConfidenceSection confidenceRange={data.confidenceRange} />

      {/* Signature SVG: confidence-band breathing */}
      <div style={pageStyles.signatureSvgWrapper}>
        <SignatureSVG
          pointFormatted={data.confidenceRange.pointFormatted}
          lowFormatted={data.confidenceRange.lowFormatted}
          highFormatted={data.confidenceRange.highFormatted}
          point={data.confidenceRange.point}
          low={data.confidenceRange.low}
          high={data.confidenceRange.high}
          level={data.confidenceRange.level}
        />
      </div>

      {/* Section 05: Historical Performance */}
      <TrendSection
        trendData={data.trendData}
        channelColor={channelColor}
        confidenceLevel={data.confidenceRange.level}
      />
    </div>
  );
};

/* ── Main Page Component ─────────────────────────────────── */
interface ChannelDetailPageProps {
  state: ChannelDetailState;
}

export const ChannelDetailPage: React.FC<ChannelDetailPageProps> = ({ state }) => {
  useEffect(() => {
    ensureFonts();
    ensureMotionStyles();
  }, []);

  return (
    <main style={pageStyles.wrapper}>
      {state.status === 'loading' && <LoadingSkeleton />}
      {state.status === 'empty' && (
        <EmptyState variant={state.emptyVariant} currentDay={state.currentDay} />
      )}
      {state.status === 'error' && <ErrorState error={state.error} />}
      {state.status === 'ready' && <ReadyState data={state.data} />}
    </main>
  );
};

export default ChannelDetailPage;
