/**
 * A6-VICTOR: Channel Comparison — Canonical Implementation
 *
 * Matched to golden reference screenshot (chann Comp.png) + Channel Comp Design.md.
 *
 * Page sections (top to bottom):
 * 1. Header: "Welcome Back, Director" + "Channel Comparison"
 * 2. Recommendation banner (light BLUE) + action buttons
 * 3. Three bento-box platform cards (Google / Meta / Pinterest)
 * 4. ROAS confidence ranges chart (2/3) + "Why this matters" sidebar (1/3)
 * 5. Detailed comparison table (2/3) + "Why this model recommendation" sidebar (1/3)
 *
 * State machine: loading → empty (4 variants) → error → ready
 * Background: transparent (GeometricBackground shows through from App shell)
 */

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { getPlatformLogo } from '@/pages/channel-comparison/shared/platform-logos';
import type {
  ChannelComparisonState,
  ChannelComparisonEntry,
  ComparisonEmptyVariant,
  ConfidenceTier,
  SkeldirError,
} from '@/pages/channel-comparison/shared/types';

// ---------------------------------------------------------------------------
// Confidence tokens
// ---------------------------------------------------------------------------

const CONF_BADGE: Record<ConfidenceTier, { label: string; bg: string; text: string; border: string }> = {
  high: { label: 'High Confidence', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  medium: { label: 'Medium Confidence', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  low: { label: 'Low Confidence', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

const CONF_GRADIENT: Record<ConfidenceTier, { from: string; to: string }> = {
  high: { from: '#0d9488', to: '#10b981' },
  medium: { from: '#059669', to: '#34d399' },
  low: { from: '#d97706', to: '#fbbf24' },
};

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

const LoadingSkeleton: React.FC = () => (
  <div className="space-y-6 animate-pulse">
    <div className="space-y-2">
      <div className="h-4 w-40 rounded bg-gray-200" />
      <div className="h-7 w-56 rounded bg-gray-200" />
    </div>
    <div className="h-16 rounded-xl bg-blue-50" />
    <div className="grid grid-cols-3 gap-6">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-xl bg-white/80 shadow-sm p-6 space-y-4 border border-gray-100">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-gray-200" />
            <div className="h-4 w-24 rounded bg-gray-200" />
            <div className="h-5 w-28 rounded-full bg-gray-100 ml-auto" />
          </div>
          <div className="h-14 w-24 rounded bg-gray-100" />
          <div className="h-3 w-36 rounded bg-gray-100" />
          <div className="flex justify-between pt-3 border-t border-gray-100">
            <div className="h-3 w-20 rounded bg-gray-100" />
            <div className="h-3 w-24 rounded bg-gray-100" />
          </div>
        </div>
      ))}
    </div>
    <div className="grid grid-cols-3 gap-6">
      <div className="col-span-2 h-44 rounded-xl bg-white/80 border border-gray-100" />
      <div className="h-44 rounded-xl bg-white/80 border border-gray-100" />
    </div>
    <div className="grid grid-cols-3 gap-6">
      <div className="col-span-2 h-52 rounded-xl bg-white/80 border border-gray-100" />
      <div className="h-52 rounded-xl bg-white/80 border border-gray-100" />
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Empty states
// ---------------------------------------------------------------------------

const EmptyState: React.FC<{ variant: ComparisonEmptyVariant }> = ({ variant }) => {
  const configs: Record<ComparisonEmptyVariant, { icon: React.ReactNode; title: string; description: string; action?: string }> = {
    'no-data-yet': {
      icon: <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-gray-400"><path d="M12 2v4m0 12v4M2 12h4m12 0h4" strokeLinecap="round" /><circle cx="12" cy="12" r="3" /></svg>,
      title: 'Connect your first platform to begin attribution modeling.',
      description: 'Channel comparison requires at least two connected ad platforms and a revenue source.',
      action: 'Connect Platform',
    },
    'building-model': {
      icon: <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-primary"><circle cx="12" cy="12" r="10" strokeDasharray="4 4" /><path d="M12 6v6l4 2" strokeLinecap="round" /></svg>,
      title: 'Attribution model building — accumulating evidence.',
      description: 'The model requires at least 14 days of data from connected channels.',
    },
    'insufficient-selection': {
      icon: <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-gray-400"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" strokeDasharray="3 3" /><rect x="3" y="14" width="7" height="7" rx="1" strokeDasharray="3 3" /></svg>,
      title: 'Select at least two channels to compare.',
      description: 'Use the channel selector to pick 2–4 channels for side-by-side comparison.',
    },
    'no-results-filter': {
      icon: <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-gray-400"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35M8 8l6 6M14 8l-6 6" strokeLinecap="round" /></svg>,
      title: 'No channels match this date range.',
      description: 'Adjust the date range or clear filters to see comparison data.',
      action: 'Clear Filters',
    },
  };
  const c = configs[variant];
  return (
    <div className="flex flex-col items-center justify-center py-24 px-8 text-center rounded-xl bg-white/80 backdrop-blur-sm border border-gray-100 shadow-sm">
      <div className="mb-5 opacity-60">{c.icon}</div>
      <h3 className="text-base font-semibold text-foreground mb-2">{c.title}</h3>
      <p className="text-sm text-muted-foreground max-w-md leading-relaxed">{c.description}</p>
      {c.action && (
        <button className="mt-5 px-5 py-2.5 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity">{c.action}</button>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

const ErrorState: React.FC<{ error: SkeldirError }> = ({ error }) => (
  <div className="flex flex-col items-center justify-center py-24 px-8 text-center rounded-xl bg-white/80 backdrop-blur-sm border border-gray-100 shadow-sm">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="text-destructive mb-5">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
    <h3 className="text-base font-semibold text-foreground mb-2">Comparison data temporarily unavailable.</h3>
    <p className="text-sm text-muted-foreground max-w-md leading-relaxed mb-1">{error.message}</p>
    <p className="text-xs font-mono text-muted-foreground/60 mb-5">Correlation ID: {error.correlationId}</p>
    <div className="flex gap-3">
      {error.retryable && error.action && (
        <button onClick={error.action.onClick} className="px-5 py-2.5 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity">{error.action.label}</button>
      )}
      <button className="px-5 py-2.5 text-sm font-medium rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">Report issue</button>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Recommendation banner (light BLUE per doc)
// ---------------------------------------------------------------------------

const RecommendationBanner: React.FC<{ summary: string; confidence: ConfidenceTier; expectedImpact: string }> = ({ summary, confidence, expectedImpact }) => {
  const badge = CONF_BADGE[confidence];
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl bg-blue-50/80 backdrop-blur-sm border border-blue-200/60 px-5 py-4 shadow-sm">
      <div className="flex items-start gap-3 min-w-0">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-blue-500 mt-0.5 shrink-0"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" strokeLinecap="round" /></svg>
        <div>
          <p className="text-xs font-semibold text-blue-800 uppercase tracking-wide mb-1">Recommended budget shift</p>
          <p className="text-sm text-gray-800 leading-relaxed">
            {summary}.{' '}
            <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium border', badge.bg, badge.text, badge.border)}>{badge.label}</span>
            , estimated {expectedImpact}.
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button className="px-4 py-2 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity whitespace-nowrap">Review in Budget Optimizer</button>
        <button className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition-colors whitespace-nowrap">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
          Export Comparison
        </button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Bento-box platform card
// ---------------------------------------------------------------------------

const PlatformCard: React.FC<{ channel: ChannelComparisonEntry }> = ({ channel }) => {
  const Logo = getPlatformLogo(channel.platform);
  const badge = CONF_BADGE[channel.confidence];
  const roasNumber = channel.roas.replace('$', '');

  return (
    <div className={cn('rounded-xl bg-white/90 backdrop-blur-sm border p-5 shadow-sm transition-shadow hover:shadow-md', channel.isWinner ? 'border-emerald-200 shadow-emerald-50' : 'border-gray-200/80')}>
      <div className="flex items-center gap-2.5 mb-5">
        <Logo size={24} />
        <span className="text-sm font-semibold text-foreground">{channel.channelName}</span>
        <span className={cn('ml-auto inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium border', badge.bg, badge.text, badge.border)}>{badge.label}</span>
      </div>
      <div className="mb-2">
        <span className="text-5xl font-bold font-mono text-foreground tabular-nums tracking-tight leading-none">{roasNumber}</span>
        <span className="text-base text-muted-foreground ml-2 font-medium">ROAS</span>
      </div>
      <div className="mb-5">
        {channel.isWinner ? (
          <div className="flex items-center gap-1.5 text-emerald-600">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M13.5 4.5l-7 7L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <span className="text-xs font-medium">Top performer</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M5 2v6M2.5 5.5L5 8l2.5-2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <span className="text-xs font-mono">{channel.roasVsAverage}</span>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium mb-0.5">Spend</p>
          <p className="text-sm font-mono font-semibold text-foreground tabular-nums">{channel.adSpend}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium mb-0.5">Revenue</p>
          <p className="text-sm font-mono font-semibold text-foreground tabular-nums">{channel.verifiedRevenue}</p>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// ROAS confidence ranges chart
// ---------------------------------------------------------------------------

const ConfidenceRangesChart: React.FC<{ channels: ChannelComparisonEntry[] }> = ({ channels }) => {
  const domainMin = 1.0;
  const domainMax = 5.0;
  const domainRange = domainMax - domainMin;
  const toPercent = (v: number) => ((v - domainMin) / domainRange) * 100;
  const parseRoas = (s: string) => parseFloat(s.replace('$', ''));
  const ticks = [1.0, 2.0, 3.0, 4.0, 5.0];

  return (
    <div className="rounded-xl bg-white/90 backdrop-blur-sm border border-gray-200/80 p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-foreground mb-5">ROAS confidence ranges by channel</h3>
      <div className="space-y-5 mb-3">
        {channels.map((ch) => {
          const low = parseRoas(ch.confidenceRange.low);
          const high = parseRoas(ch.confidenceRange.high);
          const point = parseRoas(ch.roas);
          const leftPct = toPercent(low);
          const widthPct = toPercent(high) - leftPct;
          const pointPct = toPercent(point);
          const gradient = CONF_GRADIENT[ch.confidence];
          const Logo = getPlatformLogo(ch.platform);

          return (
            <div key={ch.channelId}>
              <div className="flex items-center gap-2 mb-1.5">
                <Logo size={16} />
                <span className="text-xs font-medium text-foreground">{ch.channelName}</span>
              </div>
              <div className="relative h-8 bg-gray-50 rounded-md">
                <div className="absolute top-1.5 bottom-1.5 rounded-sm" style={{ left: `${leftPct}%`, width: `${Math.max(widthPct, 1)}%`, background: `linear-gradient(90deg, ${gradient.from}, ${gradient.to})`, opacity: 0.35 }} />
                <div className="absolute top-0 bottom-0 flex flex-col items-center justify-center" style={{ left: `${pointPct}%` }}>
                  <div className="w-0.5 h-full" style={{ backgroundColor: gradient.to, opacity: 0.6 }} />
                </div>
                <span className="absolute -top-4 text-[10px] font-mono font-semibold text-foreground" style={{ left: `${pointPct}%`, transform: 'translateX(-50%)' }}>{point.toFixed(2)}</span>
                <span className="absolute -bottom-4 text-[9px] font-mono text-muted-foreground" style={{ left: `${leftPct}%`, transform: 'translateX(-50%)' }}>{low.toFixed(2)}</span>
                <span className="absolute -bottom-4 text-[9px] font-mono text-muted-foreground" style={{ left: `${leftPct + widthPct}%`, transform: 'translateX(-50%)' }}>{high.toFixed(2)}</span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="relative h-5 mt-6 border-t border-gray-100 pt-1">
        {ticks.map((v) => (
          <span key={v} className="absolute text-[9px] font-mono text-muted-foreground" style={{ left: `${toPercent(v)}%`, transform: 'translateX(-50%)' }}>{v.toFixed(1)}</span>
        ))}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Sidebar panels
// ---------------------------------------------------------------------------

const WhyThisMatters: React.FC = () => (
  <div className="rounded-xl bg-white/90 backdrop-blur-sm border border-gray-200/80 p-5 shadow-sm h-full">
    <h3 className="text-sm font-semibold text-foreground mb-3">Why this matters</h3>
    <p className="text-xs text-muted-foreground leading-relaxed">The width of each confidence range indicates how certain the model is about a channel's true ROAS. Google Ads shows a tight range, meaning the model has high certainty in its performance estimate. Pinterest Ads shows a wide range — the model needs more data before it can confidently assess performance.</p>
    <p className="text-xs text-muted-foreground leading-relaxed mt-3">Channels with overlapping ranges may not have a statistically significant performance difference. The model accounts for this uncertainty when making budget shift recommendations.</p>
  </div>
);

const WhyThisRecommendation: React.FC<{ summary: string; confidence: ConfidenceTier }> = ({ summary, confidence }) => {
  const badge = CONF_BADGE[confidence];
  return (
    <div className="rounded-xl bg-white/90 backdrop-blur-sm border border-gray-200/80 p-5 shadow-sm h-full flex flex-col">
      <h3 className="text-sm font-semibold text-foreground mb-3">Why this model recommendation</h3>
      <p className="text-xs text-muted-foreground leading-relaxed flex-1">
        The model identified a budget reallocation opportunity: {summary.toLowerCase()}.
        This recommendation is based on verified attribution data — not platform-reported metrics.
        Shifting budget from lower-ROAS channels to higher-performing channels is expected to positively impact revenue. Confidence is{' '}
        <span className={cn('inline px-1 py-0.5 rounded text-[10px] font-medium', badge.bg, badge.text)}>{badge.label.toLowerCase()}</span>
        {' '}— the model recommends reviewing results after 14 days.
      </p>
      <button className="w-full mt-4 px-4 py-2.5 text-sm font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">Open in Budget Optimizer</button>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Detailed comparison table
// ---------------------------------------------------------------------------

const ComparisonTable: React.FC<{ channels: ChannelComparisonEntry[]; dateLabel: string }> = ({ channels, dateLabel }) => {
  const parseVal = (s: string) => parseFloat(s.replace(/[$k,]/g, ''));
  const bestRoas = Math.max(...channels.map((ch) => parseVal(ch.roas)));
  const bestRev = Math.max(...channels.map((ch) => parseVal(ch.verifiedRevenue)));

  return (
    <div className="rounded-xl bg-white/90 backdrop-blur-sm border border-gray-200/80 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-foreground">Detailed comparison table <span className="text-muted-foreground font-normal">({dateLabel})</span></h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              <th className="text-left px-5 py-3 text-xs font-medium text-muted-foreground">Channel</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Spend</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Revenue</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">ROAS</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Confidence</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Δ vs Best ROAS</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Δ vs Best Rev</th>
            </tr>
          </thead>
          <tbody>
            {channels.map((ch) => {
              const Logo = getPlatformLogo(ch.platform);
              const badge = CONF_BADGE[ch.confidence];
              const chRoas = parseVal(ch.roas);
              const chRev = parseVal(ch.verifiedRevenue);
              const deltaRoas = chRoas - bestRoas;
              const deltaRev = chRev - bestRev;
              return (
                <tr key={ch.channelId} className={cn('border-b border-gray-50 transition-colors', ch.isWinner ? 'bg-emerald-50/30' : 'hover:bg-gray-50/50')}>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <Logo size={18} />
                      <span className="font-medium text-foreground">{ch.channelName}</span>
                      {ch.isWinner && <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-emerald-500"><path d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z" fill="currentColor" /></svg>}
                    </div>
                  </td>
                  <td className="text-right px-4 py-3.5 font-mono text-foreground tabular-nums">{ch.adSpend}</td>
                  <td className="text-right px-4 py-3.5 font-mono text-foreground tabular-nums">{ch.verifiedRevenue}</td>
                  <td className="text-right px-4 py-3.5 font-mono font-semibold text-foreground tabular-nums">{ch.roas}</td>
                  <td className="text-center px-4 py-3.5">
                    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border', badge.bg, badge.text, badge.border)}>{badge.label}</span>
                  </td>
                  <td className="text-right px-4 py-3.5 font-mono tabular-nums">
                    {deltaRoas === 0 ? <span className="text-emerald-600 font-medium">—</span> : <span className="text-red-500">{deltaRoas.toFixed(2)}</span>}
                  </td>
                  <td className="text-right px-4 py-3.5 font-mono tabular-nums">
                    {deltaRev === 0 ? <span className="text-emerald-600 font-medium">—</span> : <span className="text-red-500">{deltaRev > 0 ? '+' : ''}{deltaRev.toFixed(1)}k</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page header
// ---------------------------------------------------------------------------

const PageHeader: React.FC = () => (
  <div>
    <p className="text-sm text-muted-foreground mb-1">Welcome Back, Director</p>
    <h1 className="text-xl font-bold text-foreground">Channel Comparison</h1>
  </div>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface A6VictorComparisonProps {
  initialState: ChannelComparisonState;
}

export const A6VictorComparison: React.FC<A6VictorComparisonProps> = ({ initialState }) => {
  const [_selectedRange] = useState('Last 30 Days');

  const shell = (children: React.ReactNode) => (
    <div className="max-w-6xl mx-auto px-8 py-6 space-y-6">{children}</div>
  );

  if (initialState.status === 'loading') return shell(<LoadingSkeleton />);
  if (initialState.status === 'empty') return shell(<><PageHeader /><EmptyState variant={initialState.variant} /></>);
  if (initialState.status === 'error') return shell(<><PageHeader /><ErrorState error={initialState.error} /></>);

  const { data } = initialState;

  return shell(
    <>
      <PageHeader />
      {data.recommendation && <RecommendationBanner summary={data.recommendation.summary} confidence={data.recommendation.confidence} expectedImpact={data.recommendation.expectedImpact} />}
      <div className="grid grid-cols-3 gap-6">
        {data.channels.map((ch) => <PlatformCard key={ch.channelId} channel={ch} />)}
      </div>
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2"><ConfidenceRangesChart channels={data.channels} /></div>
        <WhyThisMatters />
      </div>
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2"><ComparisonTable channels={data.channels} dateLabel={data.dateRange.label} /></div>
        {data.recommendation && <WhyThisRecommendation summary={data.recommendation.summary} confidence={data.recommendation.confidence} />}
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground pb-4">
        <span>Last updated: {new Date(data.lastUpdated).toLocaleString()} · {data.channels.length} channels</span>
        <span>{data.dateRange.label}</span>
      </div>
    </>
  );
};

export default A6VictorComparison;
