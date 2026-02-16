/**
 * A6-VICTOR: Channel Comparison — Reference-Faithful Implementation
 *
 * Light theme, clean SaaS dashboard. Layout from reference image:
 * 1. Page title
 * 2. Green recommendation banner
 * 3. Channel hero cards (side-by-side, large ROAS numbers)
 * 4. ROAS confidence ranges horizontal bar chart
 * 5. "Why this matters" + "Why this recommendation" explanation panels
 * 6. Detailed comparison table
 * 7. Footer with "Open in Skeldir?" link
 *
 * State machine: loading → empty (4 variants) → error → ready
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
// Confidence helpers
// ---------------------------------------------------------------------------

const CONF_BADGE: Record<ConfidenceTier, { label: string; bg: string; text: string; border: string }> = {
  high: { label: 'High Confidence', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  medium: { label: 'Medium Confidence', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  low: { label: 'Low Confidence', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

const CONF_BAR_COLOR: Record<ConfidenceTier, string> = {
  high: '#10b981',
  medium: '#f59e0b',
  low: '#ef4444',
};

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

const LoadingSkeleton: React.FC = () => (
  <div className="space-y-6 animate-pulse">
    <div className="h-7 w-52 rounded bg-gray-200" />
    <div className="h-16 rounded-lg bg-emerald-50" />
    <div className="grid grid-cols-3 gap-5">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-xl border border-gray-200 bg-white p-6 space-y-4">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded-full bg-gray-200" />
            <div className="h-4 w-24 rounded bg-gray-200" />
          </div>
          <div className="h-12 w-20 rounded bg-gray-100" />
          <div className="h-3 w-32 rounded bg-gray-100" />
          <div className="flex gap-4">
            <div className="h-3 w-20 rounded bg-gray-100" />
            <div className="h-3 w-20 rounded bg-gray-100" />
          </div>
        </div>
      ))}
    </div>
    <div className="h-40 rounded-lg bg-gray-50 border border-gray-200" />
    <div className="h-48 rounded-lg bg-gray-50 border border-gray-200" />
  </div>
);

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

const EmptyState: React.FC<{ variant: ComparisonEmptyVariant }> = ({ variant }) => {
  const configs: Record<ComparisonEmptyVariant, { icon: React.ReactNode; title: string; description: string; action?: string }> = {
    'no-data-yet': {
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round">
          <path d="M12 2v4m0 12v4M2 12h4m12 0h4" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      ),
      title: 'Connect your first platform to begin attribution modeling.',
      description: 'Channel comparison requires at least two connected ad platforms and a revenue source.',
      action: 'Connect Platform',
    },
    'building-model': {
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round">
          <circle cx="12" cy="12" r="10" strokeDasharray="4 4" />
          <path d="M12 6v6l4 2" />
        </svg>
      ),
      title: 'Attribution model building — accumulating evidence.',
      description: 'The model requires at least 14 days of data from connected channels. Comparison will be available once the first model run completes.',
    },
    'insufficient-selection': {
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" strokeDasharray="3 3" />
          <rect x="3" y="14" width="7" height="7" rx="1" strokeDasharray="3 3" />
        </svg>
      ),
      title: 'Select at least two channels to compare.',
      description: 'Use the channel selector above to pick 2–4 channels for side-by-side comparison.',
    },
    'no-results-filter': {
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35M8 8l6 6M14 8l-6 6" />
        </svg>
      ),
      title: 'No channels match this date range.',
      description: 'Adjust the date range or clear filters to see comparison data.',
      action: 'Clear Filters',
    },
  };

  const c = configs[variant];
  return (
    <div className="flex flex-col items-center justify-center py-24 px-8 text-center">
      <div className="mb-5 opacity-60">{c.icon}</div>
      <h3 className="text-base font-semibold text-gray-900 mb-2">{c.title}</h3>
      <p className="text-sm text-gray-500 max-w-md leading-relaxed">{c.description}</p>
      {c.action && (
        <button className="mt-5 px-5 py-2.5 text-sm font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">
          {c.action}
        </button>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

const ErrorState: React.FC<{ error: SkeldirError }> = ({ error }) => (
  <div className="flex flex-col items-center justify-center py-24 px-8 text-center">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" className="mb-5">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
    <h3 className="text-base font-semibold text-gray-900 mb-2">Comparison data temporarily unavailable.</h3>
    <p className="text-sm text-gray-500 max-w-md leading-relaxed mb-1">{error.message}</p>
    <p className="text-xs font-mono text-gray-400 mb-5">Correlation ID: {error.correlationId}</p>
    <div className="flex gap-3">
      {error.retryable && error.action && (
        <button
          onClick={error.action.onClick}
          className="px-5 py-2.5 text-sm font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
        >
          {error.action.label}
        </button>
      )}
      <button className="px-5 py-2.5 text-sm font-medium rounded-lg border border-gray-300 text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors">
        Report issue
      </button>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Recommendation banner (green tinted, full-width)
// ---------------------------------------------------------------------------

const RecommendationBanner: React.FC<{ summary: string; confidence: ConfidenceTier; expectedImpact: string }> = ({
  summary,
  confidence,
  expectedImpact,
}) => {
  const badge = CONF_BADGE[confidence];
  return (
    <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-5 py-3.5">
      <div className="flex items-center gap-2 mb-1">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-emerald-600">
          <path d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z" fill="currentColor" />
        </svg>
        <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wide">Recommended budget shift</span>
      </div>
      <p className="text-sm text-gray-800">
        {summary}.{' '}
        <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium border', badge.bg, badge.text, badge.border)}>
          {badge.label}
        </span>
        {', '}estimated {expectedImpact} revenue impact.
      </p>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Channel hero card
// ---------------------------------------------------------------------------

const ChannelHeroCard: React.FC<{ channel: ChannelComparisonEntry }> = ({ channel }) => {
  const Logo = getPlatformLogo(channel.platform);
  const badge = CONF_BADGE[channel.confidence];

  // Strip "$" for large display number
  const roasNumber = channel.roas.replace('$', '');

  return (
    <div
      className={cn(
        'rounded-xl border bg-white p-5 transition-shadow',
        channel.isWinner
          ? 'border-emerald-300 shadow-sm shadow-emerald-100'
          : 'border-gray-200'
      )}
    >
      {/* Header: logo + name */}
      <div className="flex items-center gap-2.5 mb-4">
        <Logo size={22} />
        <span className="text-sm font-semibold text-gray-900">{channel.channelName}</span>
        {channel.isWinner && (
          <span className="ml-auto px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-semibold uppercase tracking-wider">
            Best
          </span>
        )}
      </div>

      {/* Large ROAS */}
      <div className="mb-1">
        <span className="text-4xl font-bold font-mono text-gray-900 tabular-nums tracking-tight">
          {roasNumber}
        </span>
        <span className="text-sm text-gray-500 ml-1.5">ROAS</span>
      </div>

      {/* Confidence badge */}
      <div className="mb-4">
        <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border', badge.bg, badge.text, badge.border)}>
          {badge.label}
        </span>
      </div>

      {/* Confidence range text */}
      <p className="text-xs text-gray-500 mb-4">
        CI: {channel.confidenceRange.low}–{channel.confidenceRange.high} · ±{channel.confidenceRange.margin}%
      </p>

      {/* Metric row */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 pt-3 border-t border-gray-100">
        <MetricItem label="Spend" value={channel.adSpend} />
        <MetricItem label="Revenue" value={channel.verifiedRevenue} />
        <MetricItem label="CPA" value={channel.cpa} />
        <MetricItem label="Conversions" value={channel.conversions} />
      </div>
    </div>
  );
};

const MetricItem: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div>
    <p className="text-[10px] text-gray-400 uppercase tracking-wide font-medium">{label}</p>
    <p className="text-sm font-mono font-semibold text-gray-800 tabular-nums">{value}</p>
  </div>
);

// ---------------------------------------------------------------------------
// ROAS confidence ranges chart (horizontal bars)
// ---------------------------------------------------------------------------

const ConfidenceRangesChart: React.FC<{ channels: ChannelComparisonEntry[] }> = ({ channels }) => {
  // Parse numeric ROAS values for scaling
  const parseRoas = (s: string) => parseFloat(s.replace('$', ''));
  const allValues = channels.flatMap((ch) => [
    parseRoas(ch.confidenceRange.low),
    parseRoas(ch.confidenceRange.high),
  ]);
  const domainMin = Math.max(0, Math.min(...allValues) - 0.3);
  const domainMax = Math.max(...allValues) + 0.3;
  const range = domainMax - domainMin;

  const toPercent = (v: number) => ((v - domainMin) / range) * 100;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">ROAS confidence ranges by channel</h3>
      <div className="space-y-3">
        {channels.map((ch) => {
          const low = parseRoas(ch.confidenceRange.low);
          const high = parseRoas(ch.confidenceRange.high);
          const point = parseRoas(ch.roas);
          const leftPct = toPercent(low);
          const widthPct = toPercent(high) - leftPct;
          const pointPct = toPercent(point);
          const barColor = CONF_BAR_COLOR[ch.confidence];
          const Logo = getPlatformLogo(ch.platform);

          return (
            <div key={ch.channelId} className="flex items-center gap-3">
              {/* Channel label */}
              <div className="flex items-center gap-2 w-32 shrink-0">
                <Logo size={16} />
                <span className="text-xs font-medium text-gray-700 truncate">{ch.channelName}</span>
              </div>
              {/* Bar */}
              <div className="flex-1 relative h-7 bg-gray-50 rounded">
                {/* Range bar */}
                <div
                  className="absolute top-1 bottom-1 rounded"
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    backgroundColor: barColor,
                    opacity: 0.2,
                  }}
                />
                {/* Point estimate */}
                <div
                  className="absolute top-0 bottom-0 flex items-center"
                  style={{ left: `${pointPct}%` }}
                >
                  <div
                    className="w-2.5 h-2.5 rounded-full border-2 border-white"
                    style={{ backgroundColor: barColor }}
                  />
                </div>
                {/* Low label */}
                <span
                  className="absolute -bottom-4 text-[9px] font-mono text-gray-400"
                  style={{ left: `${leftPct}%`, transform: 'translateX(-50%)' }}
                >
                  {ch.confidenceRange.low}
                </span>
                {/* High label */}
                <span
                  className="absolute -bottom-4 text-[9px] font-mono text-gray-400"
                  style={{ left: `${leftPct + widthPct}%`, transform: 'translateX(-50%)' }}
                >
                  {ch.confidenceRange.high}
                </span>
              </div>
              {/* ROAS value */}
              <span className="text-xs font-mono font-semibold text-gray-800 w-12 text-right tabular-nums">
                {ch.roas}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Why panels (right side in reference)
// ---------------------------------------------------------------------------

const WhyThisMatters: React.FC = () => (
  <div className="rounded-xl border border-gray-200 bg-white p-5">
    <h3 className="text-sm font-semibold text-gray-900 mb-2">Why this matters</h3>
    <p className="text-xs text-gray-600 leading-relaxed">
      Understanding which channels deliver the highest verified ROAS with statistical confidence
      enables data-driven budget allocation. Channels with overlapping confidence ranges may not
      have a statistically significant performance difference — the model accounts for this
      uncertainty in its recommendations.
    </p>
  </div>
);

const WhyThisRecommendation: React.FC<{ summary: string; confidence: ConfidenceTier }> = ({ summary, confidence }) => {
  const badge = CONF_BADGE[confidence];
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-2">Why this recommendation</h3>
      <p className="text-xs text-gray-600 leading-relaxed mb-3">
        The model identified a budget reallocation opportunity: {summary.toLowerCase()}.
        This is based on verified attribution data, not platform-reported metrics.
        Shifting budget from underperforming channels to higher-ROAS channels is
        expected to positively impact revenue. Confidence is{' '}
        <span className={cn('inline px-1 py-0.5 rounded text-[10px] font-medium', badge.bg, badge.text)}>
          {badge.label.toLowerCase()}
        </span>{' '}
        — the model recommends reviewing results after 14 days.
      </p>
      <button className="text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors">
        Open in Skeldir? →
      </button>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Detailed comparison table
// ---------------------------------------------------------------------------

const ComparisonTable: React.FC<{ channels: ChannelComparisonEntry[]; dateLabel: string }> = ({ channels, dateLabel }) => (
  <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
    <div className="px-5 py-3.5 border-b border-gray-100">
      <h3 className="text-sm font-semibold text-gray-900">
        Detailed comparison table <span className="text-gray-400 font-normal">({dateLabel})</span>
      </h3>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 bg-gray-50/50">
            <th className="text-left px-5 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">Channel</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">ROAS</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">Revenue</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">Ad Spend</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">CPA</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">Conversions</th>
            <th className="text-center px-4 py-2.5 text-xs font-medium text-gray-500 uppercase tracking-wide">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {channels.map((ch) => {
            const Logo = getPlatformLogo(ch.platform);
            const badge = CONF_BADGE[ch.confidence];
            return (
              <tr key={ch.channelId} className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <Logo size={16} />
                    <span className="font-medium text-gray-900 text-sm">{ch.channelName}</span>
                    {ch.isWinner && (
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-emerald-500">
                        <path d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z" fill="currentColor" />
                      </svg>
                    )}
                  </div>
                </td>
                <td className="text-right px-4 py-3 font-mono font-semibold text-gray-900 tabular-nums">{ch.roas}</td>
                <td className="text-right px-4 py-3 font-mono text-gray-700 tabular-nums">{ch.verifiedRevenue}</td>
                <td className="text-right px-4 py-3 font-mono text-gray-700 tabular-nums">{ch.adSpend}</td>
                <td className="text-right px-4 py-3 font-mono text-gray-700 tabular-nums">{ch.cpa}</td>
                <td className="text-right px-4 py-3 font-mono text-gray-700 tabular-nums">{ch.conversions}</td>
                <td className="text-center px-4 py-3">
                  <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border', badge.bg, badge.text, badge.border)}>
                    {badge.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    <div className="px-5 py-3 border-t border-gray-100 flex justify-end">
      <button className="text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors">
        Open in Skeldir? →
      </button>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface A6VictorComparisonProps {
  initialState: ChannelComparisonState;
}

export const A6VictorComparison: React.FC<A6VictorComparisonProps> = ({ initialState }) => {
  const [selectedRange, setSelectedRange] = useState('Last 30 Days');
  const DATE_RANGES = ['7 Days', '30 Days', '60 Days', '90 Days'] as const;

  // ----- STATE MACHINE -----
  if (initialState.status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50/80 p-8 max-w-6xl mx-auto">
        <LoadingSkeleton />
      </div>
    );
  }

  if (initialState.status === 'empty') {
    return (
      <div className="min-h-screen bg-gray-50/80 p-8 max-w-6xl mx-auto">
        <h1 className="text-xl font-bold text-gray-900 mb-6">Channel Comparison</h1>
        <EmptyState variant={initialState.variant} />
      </div>
    );
  }

  if (initialState.status === 'error') {
    return (
      <div className="min-h-screen bg-gray-50/80 p-8 max-w-6xl mx-auto">
        <h1 className="text-xl font-bold text-gray-900 mb-6">Channel Comparison</h1>
        <ErrorState error={initialState.error} />
      </div>
    );
  }

  // ----- READY STATE -----
  const { data } = initialState;

  return (
    <div className="min-h-screen bg-gray-50/80">
      <div className="max-w-6xl mx-auto px-8 py-6 space-y-5">

        {/* Page header */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">Channel Comparison</h1>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-gray-200 overflow-hidden bg-white">
              {DATE_RANGES.map((range) => (
                <button
                  key={range}
                  onClick={() => setSelectedRange(`Last ${range}`)}
                  className={cn(
                    'px-3 py-1.5 text-xs font-medium transition-colors',
                    selectedRange === `Last ${range}`
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  )}
                >
                  {range}
                </button>
              ))}
            </div>
            <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
              </svg>
              Export
            </button>
          </div>
        </div>

        {/* Recommendation banner */}
        {data.recommendation && (
          <RecommendationBanner
            summary={data.recommendation.summary}
            confidence={data.recommendation.confidence}
            expectedImpact={data.recommendation.expectedImpact}
          />
        )}

        {/* Channel hero cards — side by side */}
        <div className={cn(
          'grid gap-5',
          data.channels.length <= 3 ? 'grid-cols-3' : 'grid-cols-4'
        )}>
          {data.channels.map((ch) => (
            <ChannelHeroCard key={ch.channelId} channel={ch} />
          ))}
        </div>

        {/* Middle section: confidence chart + why panels */}
        <div className="grid grid-cols-3 gap-5">
          {/* Confidence ranges — spans 2 columns */}
          <div className="col-span-2">
            <ConfidenceRangesChart channels={data.channels} />
          </div>
          {/* Why panels — right column */}
          <div className="space-y-5">
            <WhyThisMatters />
            {data.recommendation && (
              <WhyThisRecommendation
                summary={data.recommendation.summary}
                confidence={data.recommendation.confidence}
              />
            )}
          </div>
        </div>

        {/* Detailed comparison table */}
        <ComparisonTable channels={data.channels} dateLabel={data.dateRange.label} />

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-gray-400 pb-4">
          <span>
            Last updated: {new Date(data.lastUpdated).toLocaleString()} · {data.channels.length} channels
          </span>
          <span>{data.dateRange.label}</span>
        </div>
      </div>
    </div>
  );
};

export default A6VictorComparison;
