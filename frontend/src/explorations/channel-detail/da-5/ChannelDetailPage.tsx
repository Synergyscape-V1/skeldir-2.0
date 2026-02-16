/**
 * DA-5 COMPACT — Channel Detail Page
 *
 * Extreme progressive disclosure: 3 hero numbers above the fold,
 * everything else behind expandable sections. Minimalist premium aesthetic.
 */

import React, { useState } from 'react';
import type { ChannelDetailState, ChannelDetailData, ConfidenceLevel } from '../shared/types';
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
  confidence: { high: '#10D98C', medium: '#F5A623', low: '#F04E4E' } as Record<ConfidenceLevel, string>,
  border: { subtle: 'rgba(139,154,184,0.12)', default: 'rgba(139,154,184,0.24)' },
};

/* ── Traffic Light Badge ─────────────────────────────────────── */
const getHealthColor = (data: ChannelDetailData): { color: string; level: string } => {
  const disc = Math.abs(data.verification.discrepancyPercent);
  const conf = data.confidenceRange.level;
  if (conf === 'low' || disc > 15) return { color: tokens.confidence.low, level: 'Low' };
  if (conf === 'medium' || disc > 5) return { color: tokens.confidence.medium, level: 'Medium' };
  return { color: tokens.confidence.high, level: 'High' };
};

const TrafficLightBadge: React.FC<{ data: ChannelDetailData }> = ({ data }) => {
  const { color, level } = getHealthColor(data);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', padding: '24px 0' }}>
      <div
        style={{
          width: '80px',
          height: '80px',
          borderRadius: '50%',
          border: `3px solid ${color}`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: `${color}10`,
        }}
      >
        <span style={{ fontFamily: "'Syne', sans-serif", fontSize: '16px', fontWeight: 600, color }}>{level}</span>
        <span style={{ fontSize: '9px', color: tokens.text.secondary, fontFamily: "'IBM Plex Sans', sans-serif" }}>Confidence</span>
      </div>
    </div>
  );
};

/* ── Expandable Section ──────────────────────────────────────── */
const ExpandableSection: React.FC<{
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}> = ({ title, children, defaultOpen = false }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        background: tokens.bg.card,
        border: `1px solid ${tokens.border.subtle}`,
        borderRadius: '8px',
        overflow: 'hidden',
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          padding: '16px 20px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: tokens.text.primary,
          fontFamily: "'IBM Plex Sans', sans-serif",
          fontSize: '14px',
          fontWeight: 500,
        }}
        aria-expanded={open}
      >
        {title}
        <span
          style={{
            transition: 'transform 300ms cubic-bezier(0.4,0,0.2,1)',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            color: tokens.text.muted,
            fontSize: '12px',
          }}
        >
          ▾
        </span>
      </button>
      <div
        style={{
          maxHeight: open ? '800px' : '0px',
          overflow: 'hidden',
          transition: 'max-height 300ms cubic-bezier(0.4,0,0.2,1)',
        }}
      >
        <div style={{ padding: '0 20px 20px' }}>{children}</div>
      </div>
    </div>
  );
};

/* ── Skeleton ─────────────────────────────────────────────────── */
const Skeleton: React.FC<{ width?: string; height?: string }> = ({ width = '100%', height = '20px' }) => (
  <>
    <style>{`
      @keyframes da5-shimmer {
        0% { background-position: -200px 0; }
        100% { background-position: calc(200px + 100%) 0; }
      }
    `}</style>
    <div
      style={{
        width,
        height,
        borderRadius: '8px',
        background: `linear-gradient(90deg, ${tokens.bg.nested} 25%, ${tokens.bg.elevated} 50%, ${tokens.bg.nested} 75%)`,
        backgroundSize: '200px 100%',
        animation: 'da5-shimmer 1.5s infinite linear',
      }}
    />
  </>
);

/* ── Empty Messages ───────────────────────────────────────────── */
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
          minHeight: 'calc(100vh - 48px)',
          fontFamily: "'IBM Plex Sans', sans-serif",
          color: tokens.text.primary,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <div style={{ width: '100%', maxWidth: '720px', padding: '32px 24px 64px' }}>
          {/* Loading */}
          {state.status === 'loading' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', alignItems: 'center', paddingTop: '48px' }}>
              <Skeleton width="200px" height="24px" />
              <Skeleton width="80px" height="80px" />
              <div style={{ display: 'flex', gap: '48px', width: '100%', justifyContent: 'center' }}>
                {[1, 2, 3].map((i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                    <Skeleton width="80px" height="36px" />
                    <Skeleton width="60px" height="14px" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty */}
          {state.status === 'empty' && (
            <div style={{ textAlign: 'center', paddingTop: '96px' }}>
              <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: '20px', fontWeight: 600, margin: '0 0 12px' }}>
                {EMPTY_MESSAGES[state.emptyVariant]?.title ?? 'No data available'}
              </h2>
              <p style={{ color: tokens.text.secondary, fontSize: '14px', margin: 0, lineHeight: 1.6 }}>
                {state.emptyVariant === 'building-model' && state.currentDay !== undefined
                  ? `Day ${state.currentDay} of 14 — ${EMPTY_MESSAGES[state.emptyVariant].message}`
                  : EMPTY_MESSAGES[state.emptyVariant]?.message}
              </p>
            </div>
          )}

          {/* Error */}
          {state.status === 'error' && (
            <div style={{ textAlign: 'center', paddingTop: '96px', maxWidth: '420px', margin: '0 auto' }}>
              <div
                style={{
                  background: tokens.bg.card,
                  border: `1px solid rgba(240,78,78,0.2)`,
                  borderRadius: '12px',
                  padding: '40px 32px',
                }}
              >
                <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: '18px', fontWeight: 600, margin: '0 0 8px', color: '#F04E4E' }}>
                  {state.error.title}
                </h2>
                <p style={{ color: tokens.text.secondary, fontSize: '14px', margin: '0 0 12px', lineHeight: 1.6 }}>
                  {state.error.message}
                </p>
                <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px', color: tokens.text.muted, margin: '0 0 20px' }}>
                  Error ID: {state.error.correlationId}
                </p>
                {state.error.retryable && (
                  <button
                    onClick={() => window.location.reload()}
                    style={{
                      background: tokens.brand,
                      color: '#fff',
                      border: 'none',
                      borderRadius: '8px',
                      padding: '10px 24px',
                      fontSize: '14px',
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
                      borderRadius: '8px',
                      padding: '10px 24px',
                      fontSize: '14px',
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <ChannelHeader channel={data.channel} dateRange={data.dateRange} />

      <TrafficLightBadge data={data} />

      {/* Hero Numbers */}
      <PerformanceMetrics performance={data.performance} mode="hero" />

      {/* Expandable sections */}
      <ExpandableSection title="Performance Details">
        <PerformanceMetrics performance={data.performance} mode="expanded" />
      </ExpandableSection>

      <ExpandableSection title="Revenue Verification">
        <VerificationSection verification={data.verification} channelName={data.channel.name} />
      </ExpandableSection>

      <ExpandableSection title="Model Confidence">
        <ConfidenceSection confidenceRange={data.confidenceRange} />
      </ExpandableSection>

      <ExpandableSection title="Historical Trend">
        <TrendSection trendData={data.trendData} channelColor={channelColor} confidenceLevel={data.confidenceRange.level} expanded />
      </ExpandableSection>

      <ExpandableSection title="Verification Status">
        <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
          <SignatureSVG
            verified={data.verification.verified}
            platformClaimed={data.verification.platformClaimed}
            confidenceLevel={data.confidenceRange.level}
          />
        </div>
      </ExpandableSection>
    </div>
  );
};

export default ChannelDetailPage;
