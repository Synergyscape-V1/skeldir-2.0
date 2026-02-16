/**
 * Final Single Channel Detail — Composed Page
 *
 * Hybrid of winning components from 5 design agents:
 * - Header: DA-1 Cockpit (+ Meta Ads SVG logo)
 * - KPI Tiles: DA-2 Dossier styling, DA-1 Cockpit horizontal layout
 * - ROAS Trend: DA-3 Timeline
 * - Confidence Range: DA-1 Cockpit
 * - Sync Heartbeat: DA-1 Cockpit
 *
 * Light theme first. All values pre-formatted — no client-side statistics.
 * Full state coverage: loading / empty / error / ready.
 */

import React from 'react';
import type { ChannelDetailState, ChannelDetailData } from '@/explorations/channel-detail/shared/types';
import { tokens, CHANNEL_COLORS, FONT_IMPORT } from './tokens';
import { ChannelHeader } from './components/ChannelHeader';
import { PerformanceMetrics } from './components/PerformanceMetrics';
import { TrendSection } from './components/TrendSection';
import { ConfidenceSection } from './components/ConfidenceSection';
import { SyncHeartbeat } from './components/SyncHeartbeat';

/* ── Skeleton ─────────────────────────────────────────────────── */
const Skeleton: React.FC<{ width?: string; height?: string }> = ({ width = '100%', height = '20px' }) => (
  <>
    <style>{`
      @keyframes finalShimmer {
        0% { background-position: -200px 0; }
        100% { background-position: calc(200px + 100%) 0; }
      }
    `}</style>
    <div
      style={{
        width,
        height,
        borderRadius: tokens.radius.md,
        background: `linear-gradient(90deg, ${tokens.bg.nested} 25%, ${tokens.bg.elevated} 50%, ${tokens.bg.nested} 75%)`,
        backgroundSize: '200px 100%',
        animation: 'finalShimmer 1.5s infinite linear',
      }}
    />
  </>
);

const LoadingState: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
    <Skeleton height="80px" />
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
      {[1, 2, 3, 4].map((i) => <Skeleton key={i} height="120px" />)}
    </div>
    <Skeleton height="320px" />
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
      <Skeleton height="240px" />
      <Skeleton height="240px" />
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

/* ── Main Component ───────────────────────────────────────────── */
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
          minHeight: '100%',
          fontFamily: tokens.font.body,
          color: tokens.text.primary,
          padding: '24px',
        }}
      >
        <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
          {/* Loading */}
          {state.status === 'loading' && <LoadingState />}

          {/* Empty */}
          {state.status === 'empty' && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
              <div
                style={{
                  background: tokens.bg.card,
                  border: `1px solid ${tokens.border.default}`,
                  borderRadius: tokens.radius.lg,
                  padding: '48px',
                  textAlign: 'center',
                  maxWidth: '420px',
                  boxShadow: tokens.shadow.md,
                }}
              >
                <h2 style={{ fontFamily: tokens.font.heading, fontSize: '20px', fontWeight: 600, margin: '0 0 12px', color: tokens.text.primary }}>
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

          {/* Error */}
          {state.status === 'error' && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
              <div
                style={{
                  background: tokens.bg.card,
                  border: `1px solid ${tokens.border.default}`,
                  borderLeft: `4px solid ${tokens.negative}`,
                  borderRadius: tokens.radius.md,
                  padding: '32px',
                  maxWidth: '480px',
                  boxShadow: tokens.shadow.md,
                }}
              >
                <h2 style={{ fontFamily: tokens.font.heading, fontSize: '18px', fontWeight: 600, margin: '0 0 8px', color: tokens.negative }}>
                  {state.error.title}
                </h2>
                <p style={{ color: tokens.text.secondary, fontSize: '14px', margin: '0 0 12px', lineHeight: 1.6 }}>
                  {state.error.message}
                </p>
                <p style={{ fontFamily: tokens.font.mono, fontSize: '11px', color: tokens.text.muted, margin: '0 0 16px' }}>
                  Error ID: {state.error.correlationId}
                </p>
                {state.error.retryable && (
                  <button
                    onClick={() => window.location.reload()}
                    style={{
                      background: tokens.brand,
                      color: tokens.text.inverse,
                      border: 'none',
                      borderRadius: tokens.radius.sm,
                      padding: '8px 20px',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontFamily: tokens.font.body,
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
                      borderRadius: tokens.radius.sm,
                      padding: '8px 20px',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontFamily: tokens.font.body,
                    }}
                  >
                    {state.error.action.label}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Ready */}
          {state.status === 'ready' && <ReadyState data={state.data} />}
        </div>
      </div>
    </>
  );
};

/* ── Ready State ──────────────────────────────────────────────── */
const ReadyState: React.FC<{ data: ChannelDetailData }> = ({ data }) => {
  const channelColor = CHANNEL_COLORS[data.channel.platform] ?? CHANNEL_COLORS['other'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header: Cockpit design + Meta Ads logo */}
      <ChannelHeader
        channel={data.channel}
        dateRange={data.dateRange}
        modelInfo={data.modelInfo}
      />

      {/* KPI Tiles: Dossier styling + Cockpit horizontal layout */}
      <PerformanceMetrics
        performance={data.performance}
        verification={data.verification}
      />

      {/* ROAS Trend: Timeline component */}
      <TrendSection
        trendData={data.trendData}
        channelColor={channelColor}
        confidenceLevel={data.confidenceRange.level}
      />

      {/* Bottom row: Confidence + Heartbeat side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* ROAS Confidence: Cockpit component */}
        <ConfidenceSection confidenceRange={data.confidenceRange} />

        {/* Sync Heartbeat: Cockpit component */}
        <SyncHeartbeat
          confidenceLevel={data.confidenceRange.level}
          lastUpdatedFormatted={data.modelInfo.lastUpdatedFormatted}
          channelColor={channelColor}
        />
      </div>
    </div>
  );
};

export default ChannelDetailPage;
