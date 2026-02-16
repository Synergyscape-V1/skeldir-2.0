/**
 * A3PrismComparison — Split-Pane Comparator (main root component)
 *
 * Design territory: side-by-side vertical channel panels.
 * Think "multi-monitor trading desk" — each channel gets its own
 * screen/panel in a responsive CSS grid (2–4 columns).
 *
 * Implements the full 4-state machine:
 *   loading  -> skeleton panels
 *   empty    -> contextual message per variant with icon and CTA
 *   error    -> correlationId + retry button
 *   ready    -> header, recommendation, channel panes grid, footer
 *
 * @module A3-PRISM / A3PrismComparison
 */

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type {
  ChannelComparisonState,
  ChannelComparisonData,
  ComparisonEmptyVariant,
} from '@/pages/channel-comparison/shared/types';
import { COMPARISON_FIXTURES } from '@/pages/channel-comparison/shared/mock-data';
import { ChannelPane } from './ChannelPane';

// ---------------------------------------------------------------------------
// Date Range Presets
// ---------------------------------------------------------------------------

const DATE_PRESETS = [
  { label: '7 days', value: 7 },
  { label: '30 days', value: 30 },
  { label: '60 days', value: 60 },
  { label: '90 days', value: 90 },
] as const;

// ---------------------------------------------------------------------------
// Empty State Variants
// ---------------------------------------------------------------------------

interface EmptyConfig {
  icon: React.ReactNode;
  title: string;
  description: string;
  cta?: string;
}

const EMPTY_VARIANTS: Record<ComparisonEmptyVariant, EmptyConfig> = {
  'no-data-yet': {
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
      </svg>
    ),
    title: 'No comparison data yet',
    description:
      'Connect your first advertising channel to start seeing side-by-side attribution comparisons.',
    cta: 'Connect a channel',
  },
  'building-model': {
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground">
        <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
    title: 'Building attribution model',
    description:
      'Your channels are connected but need at least 14 days of data to produce reliable comparisons. Check back soon.',
  },
  'insufficient-selection': {
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
      </svg>
    ),
    title: 'Select channels to compare',
    description:
      'Choose at least two channels from the selector above to generate a side-by-side comparison.',
    cta: 'Select channels',
  },
  'no-results-filter': {
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
        <line x1="8" y1="11" x2="14" y2="11" />
      </svg>
    ),
    title: 'No matching results',
    description:
      'Your current filters returned no channels. Try adjusting the date range or removing filters.',
    cta: 'Clear filters',
  },
};

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

const SkeletonPane: React.FC = () => (
  <div className="flex animate-pulse flex-col gap-2 rounded-lg border border-border bg-background p-3">
    {/* Accent bar */}
    <div className="h-1 w-full rounded-full bg-muted" />
    {/* Header */}
    <div className="flex items-center gap-2">
      <div className="h-5 w-5 rounded-full bg-muted" />
      <div className="h-4 flex-1 rounded bg-muted" />
      <div className="h-2.5 w-2.5 rounded-full bg-muted" />
    </div>
    {/* Metric cards */}
    {Array.from({ length: 5 }).map((_, i) => (
      <div key={i} className="rounded-md border border-border bg-card px-3 py-2.5">
        <div className="h-2.5 w-20 rounded bg-muted" />
        <div className="mt-2 h-5 w-16 rounded bg-muted" />
        {i < 2 && (
          <>
            <div className="mt-1.5 h-2 w-24 rounded bg-muted" />
            <div className="mt-2 h-1.5 w-full rounded-full bg-muted" />
          </>
        )}
      </div>
    ))}
    {/* Trend skeleton */}
    <div className="rounded-md border border-border bg-card px-3 py-2.5">
      <div className="h-2.5 w-16 rounded bg-muted" />
      <div className="mt-2 h-9 w-full rounded bg-muted" />
    </div>
    {/* Verification skeleton */}
    <div className="rounded-md border border-border bg-card px-3 py-2.5">
      <div className="h-2.5 w-20 rounded bg-muted" />
      <div className="mt-2 space-y-1.5">
        <div className="h-3 w-full rounded bg-muted" />
        <div className="h-3 w-full rounded bg-muted" />
        <div className="h-3 w-3/4 rounded bg-muted" />
      </div>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export interface A3PrismComparisonProps {
  /** Injected state — defaults to COMPARISON_FIXTURES.ready */
  initialState?: ChannelComparisonState;
  className?: string;
}

export const A3PrismComparison: React.FC<A3PrismComparisonProps> = ({
  initialState,
  className,
}) => {
  const [state, setState] = useState<ChannelComparisonState>(
    initialState ?? (COMPARISON_FIXTURES.ready as ChannelComparisonState),
  );

  const [selectedPreset, setSelectedPreset] = useState(30);

  // ------------------------------------------
  // Handlers
  // ------------------------------------------

  const handleRetry = useCallback(() => {
    setState({ status: 'loading' });
    // Simulate re-fetch
    setTimeout(() => {
      setState(COMPARISON_FIXTURES.ready as ChannelComparisonState);
    }, 1500);
  }, []);

  const handleExport = useCallback(() => {
    if (state.status !== 'ready') return;
    const blob = new Blob(
      [JSON.stringify(state.data, null, 2)],
      { type: 'application/json' },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `skeldir-channel-comparison-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [state]);

  const handleDatePreset = useCallback((days: number) => {
    setSelectedPreset(days);
    // In production, this would trigger a data refetch
  }, []);

  // ------------------------------------------
  // Format last-updated for display
  // ------------------------------------------

  const formatTimestamp = (iso: string): string => {
    try {
      const d = new Date(iso);
      return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return iso;
    }
  };

  // ------------------------------------------
  // Render: Loading
  // ------------------------------------------

  if (state.status === 'loading') {
    return (
      <div className={cn('w-full', className)}>
        <Header
          selectedPreset={selectedPreset}
          onPresetChange={handleDatePreset}
          onExport={handleExport}
          disabled
        />
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonPane key={i} />
          ))}
        </div>
      </div>
    );
  }

  // ------------------------------------------
  // Render: Empty
  // ------------------------------------------

  if (state.status === 'empty') {
    const config = EMPTY_VARIANTS[state.variant];
    return (
      <div className={cn('w-full', className)}>
        <Header
          selectedPreset={selectedPreset}
          onPresetChange={handleDatePreset}
          onExport={handleExport}
          disabled
        />
        <div className="mx-auto mt-16 flex max-w-md flex-col items-center text-center">
          <div className="mb-4">{config.icon}</div>
          <h2 className="font-sans text-lg font-semibold text-foreground">
            {config.title}
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {config.description}
          </p>
          {config.cta && (
            <button
              type="button"
              className="mt-6 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              {config.cta}
            </button>
          )}
        </div>
      </div>
    );
  }

  // ------------------------------------------
  // Render: Error
  // ------------------------------------------

  if (state.status === 'error') {
    const { error } = state;
    return (
      <div className={cn('w-full', className)}>
        <Header
          selectedPreset={selectedPreset}
          onPresetChange={handleDatePreset}
          onExport={handleExport}
          disabled
        />
        <div className="mx-auto mt-16 flex max-w-md flex-col items-center text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-500/10">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-red-500"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 className="font-sans text-lg font-semibold text-foreground">
            Something went wrong
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {error.message}
          </p>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground/60">
            Correlation ID: {error.correlationId}
          </p>
          {error.retryable && (
            <button
              type="button"
              onClick={error.action?.onClick ?? handleRetry}
              className="mt-6 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              {error.action?.label ?? 'Retry'}
            </button>
          )}
        </div>
      </div>
    );
  }

  // ------------------------------------------
  // Render: Ready
  // ------------------------------------------

  const { data } = state;

  return (
    <div className={cn('w-full', className)}>
      {/* Header */}
      <Header
        selectedPreset={selectedPreset}
        onPresetChange={handleDatePreset}
        onExport={handleExport}
        dateLabel={data.dateRange.label}
      />

      {/* Recommendation Banner */}
      {data.recommendation && (
        <RecommendationBanner recommendation={data.recommendation} />
      )}

      {/* Channel Panes Grid */}
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
        {data.channels.map((channel) => (
          <ChannelPane
            key={channel.channelId}
            channel={channel}
            lastUpdated={data.lastUpdated}
          />
        ))}
      </div>

      {/* Last Updated Footer */}
      <footer className="mt-4 flex items-center justify-between border-t border-border pt-3">
        <p className="text-xs text-muted-foreground">
          Last updated: {formatTimestamp(data.lastUpdated)}
        </p>
        <p className="font-mono text-[10px] text-muted-foreground/50">
          A3-PRISM &middot; Split-Pane Comparator
        </p>
      </footer>
    </div>
  );
};

A3PrismComparison.displayName = 'A3PrismComparison';

// ---------------------------------------------------------------------------
// Internal: Header
// ---------------------------------------------------------------------------

interface HeaderProps {
  selectedPreset: number;
  onPresetChange: (days: number) => void;
  onExport: () => void;
  dateLabel?: string;
  disabled?: boolean;
}

const Header: React.FC<HeaderProps> = ({
  selectedPreset,
  onPresetChange,
  onExport,
  dateLabel,
  disabled,
}) => (
  <div className="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 className="font-sans text-xl font-bold text-foreground">
        Channel Comparison
      </h1>
      {dateLabel && (
        <p className="mt-0.5 text-xs text-muted-foreground">{dateLabel}</p>
      )}
    </div>
    <div className="flex items-center gap-2">
      {/* Date Range Presets */}
      <div className="flex overflow-hidden rounded-md border border-border">
        {DATE_PRESETS.map(({ label, value }) => (
          <button
            key={value}
            type="button"
            disabled={disabled}
            onClick={() => onPresetChange(value)}
            className={cn(
              'px-3 py-1.5 text-xs font-medium transition-colors',
              'disabled:cursor-not-allowed disabled:opacity-50',
              selectedPreset === value
                ? 'bg-primary text-primary-foreground'
                : 'bg-background text-muted-foreground hover:bg-muted',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Export */}
      <button
        type="button"
        onClick={onExport}
        disabled={disabled}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition-colors',
          'hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50',
        )}
        aria-label="Export comparison data"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        Export
      </button>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Internal: RecommendationBanner
// ---------------------------------------------------------------------------

interface RecommendationBannerProps {
  recommendation: NonNullable<ChannelComparisonData['recommendation']>;
}

const RECOMMENDATION_BORDER: Record<string, string> = {
  high: 'border-emerald-500/40',
  medium: 'border-amber-500/40',
  low: 'border-red-500/40',
};

const RECOMMENDATION_BG: Record<string, string> = {
  high: 'bg-emerald-500/5',
  medium: 'bg-amber-500/5',
  low: 'bg-red-500/5',
};

const RECOMMENDATION_BADGE: Record<string, string> = {
  high: 'bg-emerald-500/10 text-emerald-500',
  medium: 'bg-amber-500/10 text-amber-500',
  low: 'bg-red-500/10 text-red-500',
};

const RecommendationBanner: React.FC<RecommendationBannerProps> = ({
  recommendation,
}) => (
  <div
    className={cn(
      'mt-4 flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3',
      RECOMMENDATION_BORDER[recommendation.confidence],
      RECOMMENDATION_BG[recommendation.confidence],
    )}
  >
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0 text-primary"
      aria-hidden="true"
    >
      <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 12 18.469c-.59 0-1.164.172-1.655.493l-.013.008-.547-.547z" />
    </svg>
    <div className="flex-1">
      <p className="text-sm font-medium text-foreground">
        {recommendation.summary}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">
        Expected impact: {recommendation.expectedImpact}
      </p>
    </div>
    <span
      className={cn(
        'rounded-full px-2.5 py-0.5 text-[10px] font-semibold capitalize',
        RECOMMENDATION_BADGE[recommendation.confidence],
      )}
    >
      {recommendation.confidence} confidence
    </span>
  </div>
);

export default A3PrismComparison;
