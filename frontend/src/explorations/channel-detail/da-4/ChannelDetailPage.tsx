/**
 * DA-4 ANALYST — Channel Detail Page
 *
 * Split-pane analyst workstation: left panel (metrics + confidence + trend),
 * right panel (verification + discrepancy SVG + model info).
 * Handles all 4 states: loading, empty, error, ready.
 */

import React from 'react';
import type { ChannelDetailState, ChannelDetailData } from '../shared/types';
import { CHANNEL_COLORS } from '../shared/types';
import { ChannelHeader } from './components/ChannelHeader';
import { PerformanceMetrics } from './components/PerformanceMetrics';
import { ConfidenceSection } from './components/ConfidenceSection';
import { VerificationSection } from './components/VerificationSection';
import { TrendSection } from './components/TrendSection';
import { SignatureSVG } from './components/SignatureSVG';

const FONT_IMPORT = '@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");';

const tokens = {
  bg: { page: '#0A0E1A', card: '#111827', nested: '#1F2937', elevated: '#263244' },
  text: { primary: '#F0F4FF', secondary: '#8B9AB8', muted: '#4A5568' },
  brand: '#3D7BF5',
  border: { subtle: 'rgba(139,154,184,0.12)', default: 'rgba(139,154,184,0.24)' },
};

/* ── Skeleton ─────────────────────────────────────────────────── */
const Skeleton: React.FC<{ width?: string; height?: string }> = ({ width = '100%', height = '20px' }) => (
  <>
    <style>{`
      @keyframes da4-shimmer {
        0% { background-position: -200px 0; }
        100% { background-position: calc(200px + 100%) 0; }
      }
    `}</style>
    <div
      style={{
        width,
        height,
        borderRadius: '6px',
        background: `linear-gradient(90deg, ${tokens.bg.nested} 25%, ${tokens.bg.elevated} 50%, ${tokens.bg.nested} 75%)`,
        backgroundSize: '200px 100%',
        animation: 'da4-shimmer 1.5s infinite linear',
      }}
    />
  </>
);

const LoadingState: React.FC = () => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', padding: '24px' }}>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <Skeleton height="80px" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        {[1, 2, 3, 4].map((i) => <Skeleton key={i} height="100px" />)}
      </div>
      <Skeleton height="200px" />
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <Skeleton height="180px" />
      <Skeleton height="120px" />
      <Skeleton height="80px" />
    </div>
  </div>
);

/* ── Empty State ──────────────────────────────────────────────── */
const EMPTY_MESSAGES: Record<string, { title: string; message: string }> = {
  'no-data-yet': {
    title: 'No channel data available',
    message: 'Connect your first platform to begin attribution modeling.',
  },
  'building-model': {
    title: 'Building your attribution model',
    message: 'Accumulating evidence for your first model.',
  },
  'no-results-filter': {
    title: 'No channels match this filter',
    message: 'Adjust your filters or date range to see results.',
  },
  'feature-locked': {
    title: 'Channel Detail is not available',
    message: 'Available on Agency plan. Contact your account manager to upgrade.',
  },
};

interface ChannelDetailPageProps {
  state: ChannelDetailState;
}

export const ChannelDetailPage: React.FC<ChannelDetailPageProps> = ({ state }) => {
  return (
    <>
      <style>{FONT_IMPORT}</style>
      <div
        style={{
          background: tokens.bg.page,
          minHeight: 'calc(100vh - 48px)',
          fontFamily: "'IBM Plex Sans', sans-serif",
          color: tokens.text.primary,
        }}
      >
        {state.status === 'loading' && <LoadingState />}

        {state.status === 'empty' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', padding: '24px' }}>
            <div
              style={{
                background: tokens.bg.card,
                border: `1px solid ${tokens.border.subtle}`,
                borderRadius: '8px',
                padding: '48px',
                textAlign: 'center',
                maxWidth: '420px',
              }}
            >
              <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: '20px', fontWeight: 600, margin: '0 0 12px' }}>
                {EMPTY_MESSAGES[state.emptyVariant]?.title ?? 'No data available'}
              </h2>
              <p style={{ color: tokens.text.secondary, fontSize: '14px', margin: 0, lineHeight: 1.6 }}>
                {state.emptyVariant === 'building-model' && state.currentDay !== undefined
                  ? `Day ${state.currentDay} of 14 — ${EMPTY_MESSAGES[state.emptyVariant].message}`
                  : EMPTY_MESSAGES[state.emptyVariant]?.message}
              </p>
            </div>
          </div>
        )}

        {state.status === 'error' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', padding: '24px' }}>
            <div
              style={{
                background: tokens.bg.card,
                border: `1px solid rgba(240,78,78,0.3)`,
                borderLeft: `3px solid #F04E4E`,
                borderRadius: '8px',
                padding: '32px',
                maxWidth: '480px',
              }}
            >
              <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: '18px', fontWeight: 600, margin: '0 0 8px', color: '#F04E4E' }}>
                {state.error.title}
              </h2>
              <p style={{ color: tokens.text.secondary, fontSize: '14px', margin: '0 0 12px', lineHeight: 1.6 }}>
                {state.error.message}
              </p>
              <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px', color: tokens.text.muted, margin: '0 0 16px' }}>
                Error ID: {state.error.correlationId}
              </p>
              {state.error.retryable && (
                <button
                  onClick={() => window.location.reload()}
                  style={{
                    background: tokens.brand,
                    color: '#fff',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '8px 20px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontFamily: "'IBM Plex Sans', sans-serif",
                  }}
                >
                  Retry
                </button>
              )}
              {state.error.action && !state.error.retryable && (
                <button
                  onClick={state.error.action.onClick}
                  style={{
                    background: 'transparent',
                    color: tokens.brand,
                    border: `1px solid ${tokens.brand}`,
                    borderRadius: '6px',
                    padding: '8px 20px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontFamily: "'IBM Plex Sans', sans-serif",
                  }}
                >
                  {state.error.action.label}
                </button>
              )}
            </div>
          </div>
        )}

        {state.status === 'ready' && <ReadyState data={state.data} />}
      </div>
    </>
  );
};

/* ── Ready State — Split Pane ─────────────────────────────────── */
const ReadyState: React.FC<{ data: ChannelDetailData }> = ({ data }) => {
  const channelColor = CHANNEL_COLORS[data.channel.platform] ?? CHANNEL_COLORS['other'];

  return (
    <>
      <style>{`
        @media (max-width: 768px) {
          .da4-split-layout { grid-template-columns: 1fr !important; }
        }
      `}</style>

      {/* Full-width header */}
      <div style={{ padding: '20px 24px 0' }}>
        <ChannelHeader channel={data.channel} dateRange={data.dateRange} />
      </div>

      {/* Split panels */}
      <div
        className="da4-split-layout"
        style={{
          display: 'grid',
          gridTemplateColumns: '55% 1fr',
          gap: '1px',
          padding: '20px 24px 32px',
        }}
      >
        {/* Left Panel */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
            paddingRight: '20px',
            borderRight: `1px solid ${tokens.border.subtle}`,
          }}
        >
          <PerformanceMetrics performance={data.performance} />
          <ConfidenceSection confidenceRange={data.confidenceRange} />
          <TrendSection
            trendData={data.trendData}
            channelColor={channelColor}
            confidenceLevel={data.confidenceRange.level}
          />
        </div>

        {/* Right Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingLeft: '20px' }}>
          <VerificationSection verification={data.verification} channelName={data.channel.name} />

          <div
            style={{
              background: tokens.bg.card,
              border: `1px solid ${tokens.border.subtle}`,
              borderRadius: '8px',
              padding: '20px',
            }}
          >
            <h3 style={{ fontFamily: "'Syne', sans-serif", fontSize: '14px', fontWeight: 600, color: tokens.text.secondary, margin: '0 0 16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Discrepancy Analysis
            </h3>
            <SignatureSVG
              platformClaimed={data.verification.platformClaimed}
              platformClaimedFormatted={data.verification.platformClaimedFormatted}
              verified={data.verification.verified}
              verifiedFormatted={data.verification.verifiedFormatted}
              discrepancyPercent={data.verification.discrepancyPercent}
              discrepancyFormatted={data.verification.discrepancyFormatted}
              platformName={data.channel.name}
              revenueSource={data.verification.revenueSource}
            />
          </div>

          {/* Model Info */}
          <div
            style={{
              background: tokens.bg.card,
              border: `1px solid ${tokens.border.subtle}`,
              borderRadius: '8px',
              padding: '20px',
            }}
          >
            <h3 style={{ fontFamily: "'Syne', sans-serif", fontSize: '14px', fontWeight: 600, color: tokens.text.secondary, margin: '0 0 12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Model Info
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { label: 'Version', value: `v${data.modelInfo.version}` },
                { label: 'Last updated', value: data.modelInfo.lastUpdatedFormatted },
                { label: 'Next update', value: data.modelInfo.nextUpdate },
              ].map(({ label, value }) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '13px', color: tokens.text.secondary }}>{label}</span>
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px', color: tokens.text.primary }}>{value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ChannelDetailPage;
