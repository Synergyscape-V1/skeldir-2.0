/**
 * A1-SENTINEL: Analyst Worksheet Channel Comparison
 *
 * Design territory: Bloomberg Terminal meets quantitative research
 * - TABLE-FIRST layout with maximum data density
 * - Inline sparklines + confidence interval bars in every cell
 * - Frozen metric labels, scrollable channel columns
 * - Monospace-heavy numeric typography
 *
 * State machine: loading → empty (4 variants) → error → ready
 * All values pre-formatted by backend (Zero Mental Math).
 * No client-side statistical calculations.
 */

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import type {
  ChannelComparisonState,
  ComparisonEmptyVariant,
  ConfidenceTier,
  SkeldirError,
} from '@/pages/channel-comparison/shared/types';
import { ComparisonTable } from './ComparisonTable';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Skeleton loading state — mirrors the table structure */
const LoadingSkeleton: React.FC = () => (
  <div className="space-y-4 animate-pulse">
    {/* Header skeleton */}
    <div className="flex items-center justify-between">
      <div className="h-7 w-56 rounded bg-muted" />
      <div className="flex gap-2">
        <div className="h-8 w-28 rounded bg-muted" />
        <div className="h-8 w-28 rounded bg-muted" />
        <div className="h-8 w-20 rounded bg-muted" />
      </div>
    </div>
    {/* Table skeleton */}
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex border-b border-border p-3 gap-4">
        <div className="h-5 w-24 rounded bg-muted" />
        <div className="h-5 flex-1 rounded bg-muted" />
        <div className="h-5 flex-1 rounded bg-muted" />
        <div className="h-5 flex-1 rounded bg-muted" />
        <div className="h-5 flex-1 rounded bg-muted" />
      </div>
      {Array.from({ length: 7 }).map((_, i) => (
        <div key={i} className="flex border-b border-border/50 p-3 gap-4">
          <div className="h-4 w-24 rounded bg-muted/60" />
          <div className="h-4 flex-1 rounded bg-muted/40" />
          <div className="h-4 flex-1 rounded bg-muted/40" />
          <div className="h-4 flex-1 rounded bg-muted/40" />
          <div className="h-4 flex-1 rounded bg-muted/40" />
        </div>
      ))}
    </div>
  </div>
);

/** Empty state — contextual per variant */
const EmptyState: React.FC<{ variant: ComparisonEmptyVariant }> = ({ variant }) => {
  const configs: Record<ComparisonEmptyVariant, { icon: React.ReactNode; title: string; description: string; action?: string }> = {
    'no-data-yet': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <path d="M12 2v4m0 12v4M2 12h4m12 0h4m-3.5-6.5L17 7m-10 10-1.5 1.5M20.5 17.5 19 17M5 7 3.5 5.5" strokeLinecap="round" />
        </svg>
      ),
      title: 'Connect your first platform to begin attribution modeling.',
      description: 'Channel comparison requires at least two connected ad platforms and a revenue source.',
      action: 'Connect Platform',
    },
    'building-model': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-primary">
          <circle cx="12" cy="12" r="10" strokeDasharray="4 4" />
          <path d="M12 6v6l4 2" strokeLinecap="round" />
        </svg>
      ),
      title: 'Attribution model building — accumulating evidence.',
      description: 'The model requires at least 14 days of data from connected channels. Comparison will be available once the first model run completes.',
    },
    'insufficient-selection': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
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
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35M8 8l6 6M14 8l-6 6" strokeLinecap="round" />
        </svg>
      ),
      title: 'No channels match this date range.',
      description: 'Adjust the date range or clear filters to see comparison data.',
      action: 'Clear Filters',
    },
  };

  const config = configs[variant];
  return (
    <div className="flex flex-col items-center justify-center py-20 px-8 text-center">
      <div className="mb-4 opacity-60">{config.icon}</div>
      <h3 className="text-sm font-semibold text-foreground mb-1">{config.title}</h3>
      <p className="text-xs text-muted-foreground max-w-md leading-relaxed">{config.description}</p>
      {config.action && (
        <button className="mt-4 px-4 py-2 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          {config.action}
        </button>
      )}
    </div>
  );
};

/** Error state — what happened + why + action + correlationId */
const ErrorState: React.FC<{ error: SkeldirError }> = ({ error }) => (
  <div className="flex flex-col items-center justify-center py-20 px-8 text-center">
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-red-400 mb-4">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
    <h3 className="text-sm font-semibold text-foreground mb-1">Comparison data temporarily unavailable.</h3>
    <p className="text-xs text-muted-foreground max-w-md leading-relaxed mb-1">{error.message}</p>
    <p className="text-[10px] font-mono text-muted-foreground/60 mb-4">Correlation ID: {error.correlationId}</p>
    <div className="flex gap-2">
      {error.retryable && error.action && (
        <button
          onClick={error.action.onClick}
          className="px-4 py-2 text-xs font-medium rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          {error.action.label}
        </button>
      )}
      <button className="px-4 py-2 text-xs font-medium rounded border border-border text-muted-foreground hover:text-foreground transition-colors">
        Report issue #{error.correlationId}
      </button>
    </div>
  </div>
);

/** Winner banner */
const WinnerBanner: React.FC<{ channel: { channelName: string; winnerExplanation?: string } }> = ({ channel }) => (
  <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-emerald-500/8 border border-emerald-500/20">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-emerald-400 flex-shrink-0">
      <path d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z" fill="currentColor" />
    </svg>
    <div>
      <span className="text-xs font-semibold text-emerald-400">{channel.channelName}</span>
      <span className="text-xs text-muted-foreground ml-1.5">
        — clear performance leader.
      </span>
      {channel.winnerExplanation && (
        <span className="text-[10px] text-muted-foreground/70 ml-1">{channel.winnerExplanation}</span>
      )}
    </div>
  </div>
);

/** Recommendation card */
const RecommendationCard: React.FC<{ summary: string; confidence: ConfidenceTier; expectedImpact: string }> = ({
  summary,
  confidence,
  expectedImpact,
}) => {
  const badgeStyle: Record<ConfidenceTier, string> = {
    high: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    low: 'bg-red-500/10 text-red-400 border-red-500/20',
  };
  const labels: Record<ConfidenceTier, string> = {
    high: 'High Confidence',
    medium: 'Medium Confidence',
    low: 'Low Confidence',
  };
  return (
    <div className="flex items-center gap-4 px-4 py-3 rounded-lg bg-primary/5 border border-primary/15">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-primary flex-shrink-0">
        <path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M15 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round" opacity="0.4" />
      </svg>
      <div className="flex-1 min-w-0">
        <span className="text-xs font-semibold text-foreground">{summary}</span>
        <span className="text-xs text-muted-foreground ml-2">Expected: {expectedImpact}</span>
      </div>
      <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-mono border', badgeStyle[confidence])}>
        {labels[confidence]}
      </span>
    </div>
  );
};

/** Date range picker (simplified selector) */
const DATE_RANGES = ['Last 7 Days', 'Last 30 Days', 'Last 60 Days', 'Last 90 Days'] as const;

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface A1SentinelComparisonProps {
  initialState: ChannelComparisonState;
}

export const A1SentinelComparison: React.FC<A1SentinelComparisonProps> = ({ initialState }) => {
  const [selectedRange, setSelectedRange] = useState('Last 30 Days');

  // ---------- STATE MACHINE ----------
  if (initialState.status === 'loading') {
    return (
      <div className="space-y-6 p-6 max-w-[1440px] mx-auto">
        <LoadingSkeleton />
      </div>
    );
  }

  if (initialState.status === 'empty') {
    return (
      <div className="p-6 max-w-[1440px] mx-auto">
        <Header selectedRange={selectedRange} onRangeChange={setSelectedRange} channelCount={0} />
        <EmptyState variant={initialState.variant} />
      </div>
    );
  }

  if (initialState.status === 'error') {
    return (
      <div className="p-6 max-w-[1440px] mx-auto">
        <Header selectedRange={selectedRange} onRangeChange={setSelectedRange} channelCount={0} />
        <ErrorState error={initialState.error} />
      </div>
    );
  }

  // ---------- READY STATE ----------
  const { data } = initialState;
  const winner = data.channels.find((ch) => ch.isWinner);
  const lastUpdated = new Date(data.lastUpdated);
  const timeAgo = formatTimeAgo(lastUpdated);

  return (
    <div className="space-y-4 p-6 max-w-[1440px] mx-auto">
      {/* Header */}
      <Header
        selectedRange={selectedRange}
        onRangeChange={setSelectedRange}
        channelCount={data.channels.length}
      />

      {/* Winner banner */}
      {winner && <WinnerBanner channel={winner} />}

      {/* Recommendation */}
      {data.recommendation && (
        <RecommendationCard
          summary={data.recommendation.summary}
          confidence={data.recommendation.confidence}
          expectedImpact={data.recommendation.expectedImpact}
        />
      )}

      {/* The Table — primary element */}
      <ComparisonTable channels={data.channels} />

      {/* Footer */}
      <div className="flex items-center justify-between text-[10px] text-muted-foreground/60 font-mono px-1">
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Live · Updated {timeAgo}
        </span>
        <span>{data.dateRange.label} · {data.channels.length} channels</span>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

const Header: React.FC<{
  selectedRange: string;
  onRangeChange: (range: string) => void;
  channelCount: number;
}> = ({ selectedRange, onRangeChange, channelCount }) => (
  <div className="flex items-center justify-between flex-wrap gap-3">
    <div className="flex items-center gap-3">
      <h1 className="text-lg font-semibold text-foreground tracking-tight">
        Channel Comparison
      </h1>
      {channelCount > 0 && (
        <span className="px-2 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground">
          {channelCount} channels
        </span>
      )}
    </div>
    <div className="flex items-center gap-2">
      {/* Date range selector */}
      <div className="flex rounded-md border border-border overflow-hidden">
        {DATE_RANGES.map((range) => (
          <button
            key={range}
            onClick={() => onRangeChange(range)}
            className={cn(
              'px-3 py-1.5 text-[11px] font-medium transition-colors',
              selectedRange === range
                ? 'bg-primary text-primary-foreground'
                : 'bg-card text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            {range.replace('Last ', '')}
          </button>
        ))}
      </div>
      {/* Export button */}
      <button className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
        </svg>
        Export
      </button>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}
