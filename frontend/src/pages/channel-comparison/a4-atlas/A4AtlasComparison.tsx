/**
 * A4-ATLAS: Matrix Cockpit Channel Comparison
 *
 * Design territory: Mission Control — dense multi-metric matrix
 * - SMALL-MULTIPLES-FIRST: heatmap grid of values per channel x metric
 * - OverlapDetector hero SVG showing CI overlap/separation
 * - HIGH density: dashboard-of-dashboards
 *
 * State machine: loading -> empty (4 variants) -> error -> ready
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
import { OverlapDetector } from './OverlapDetector';
import type { OverlapChannel } from './OverlapDetector';
import { MetricMatrix } from './MetricMatrix';

// ---------------------------------------------------------------------------
// Date Range Picker
// ---------------------------------------------------------------------------

const DATE_RANGES = ['Last 7 Days', 'Last 30 Days', 'Last 60 Days', 'Last 90 Days'] as const;

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

const LoadingSkeleton: React.FC = () => (
  <div className="space-y-4 animate-pulse">
    {/* Header skeleton */}
    <div className="flex items-center justify-between">
      <div className="h-7 w-64 rounded bg-muted" />
      <div className="flex gap-2">
        <div className="h-8 w-24 rounded bg-muted" />
        <div className="h-8 w-24 rounded bg-muted" />
        <div className="h-8 w-24 rounded bg-muted" />
        <div className="h-8 w-16 rounded bg-muted" />
      </div>
    </div>
    {/* Overlap detector skeleton */}
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="h-4 w-32 rounded bg-muted mb-3" />
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="h-3 w-20 rounded bg-muted/60" />
            <div className="h-4 flex-1 rounded bg-muted/30" />
          </div>
        ))}
      </div>
    </div>
    {/* Matrix skeleton */}
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex border-b border-border p-3 gap-3">
        <div className="h-4 w-28 rounded bg-muted" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-4 flex-1 rounded bg-muted" />
        ))}
      </div>
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex border-b border-border/50 p-3 gap-3">
          <div className="h-4 w-28 rounded bg-muted/60" />
          {Array.from({ length: 5 }).map((_, j) => (
            <div key={j} className="h-4 flex-1 rounded bg-muted/30" />
          ))}
        </div>
      ))}
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

const EmptyState: React.FC<{ variant: ComparisonEmptyVariant }> = ({ variant }) => {
  const configs: Record<
    ComparisonEmptyVariant,
    { icon: React.ReactNode; title: string; description: string; action?: string }
  > = {
    'no-data-yet': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 9h18M9 3v18" strokeDasharray="3 3" />
        </svg>
      ),
      title: 'Connect platforms to populate the matrix.',
      description: 'The ATLAS matrix requires at least two connected ad platforms and a revenue source to begin channel comparison.',
      action: 'Connect Platform',
    },
    'building-model': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-primary">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 9h18" />
          <path d="M9 3v18" />
          <circle cx="15" cy="15" r="3" strokeDasharray="4 2">
            <animateTransform attributeName="transform" type="rotate" from="0 15 15" to="360 15 15" dur="3s" repeatCount="indefinite" />
          </circle>
        </svg>
      ),
      title: 'Building attribution model — matrix populating.',
      description: 'The model requires at least 14 days of data. Cells will fill as confidence ranges narrow.',
    },
    'insufficient-selection': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" strokeDasharray="3 3" />
          <rect x="3" y="14" width="7" height="7" rx="1" strokeDasharray="3 3" />
          <rect x="14" y="14" width="7" height="7" rx="1" strokeDasharray="3 3" />
        </svg>
      ),
      title: 'Select at least two channels for matrix comparison.',
      description: 'The overlap detector needs multiple channels to compare confidence intervals side-by-side.',
    },
    'no-results-filter': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 9h18M9 3v18" />
          <path d="M7 17l10-10M7 7l10 10" strokeLinecap="round" opacity="0.5" />
        </svg>
      ),
      title: 'No channels match the current filters.',
      description: 'Adjust the date range or clear filters to populate the matrix.',
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

// ---------------------------------------------------------------------------
// Error State
// ---------------------------------------------------------------------------

const ErrorState: React.FC<{ error: SkeldirError }> = ({ error }) => (
  <div className="flex flex-col items-center justify-center py-20 px-8 text-center">
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-red-400 mb-4">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
    <h3 className="text-sm font-semibold text-foreground mb-1">Matrix data temporarily unavailable.</h3>
    <p className="text-xs text-muted-foreground max-w-md leading-relaxed mb-1">{error.message}</p>
    <p className="text-[10px] font-mono text-muted-foreground/60 mb-4">
      Correlation ID: {error.correlationId}
    </p>
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

// ---------------------------------------------------------------------------
// Recommendation Strip
// ---------------------------------------------------------------------------

const RecommendationStrip: React.FC<{
  summary: string;
  confidence: ConfidenceTier;
  expectedImpact: string;
}> = ({ summary, confidence, expectedImpact }) => {
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
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        className="text-primary flex-shrink-0"
      >
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="flex-1 min-w-0">
        <span className="text-xs font-semibold text-foreground">{summary}</span>
        <span className="text-xs text-muted-foreground ml-2">Expected: {expectedImpact}</span>
      </div>
      <span
        className={cn(
          'px-1.5 py-0.5 rounded text-[10px] font-mono border flex-shrink-0',
          badgeStyle[confidence],
        )}
      >
        {labels[confidence]}
      </span>
    </div>
  );
};

// ---------------------------------------------------------------------------
// "Why this range?" Tooltip
// ---------------------------------------------------------------------------

const WhyThisRange: React.FC<{ label: string }> = ({ label }) => {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-flex">
      <button
        onClick={() => setOpen(!open)}
        onBlur={() => setOpen(false)}
        className="text-[10px] text-muted-foreground/60 hover:text-muted-foreground underline decoration-dotted underline-offset-2 cursor-help transition-colors"
        aria-label="Why this date range?"
      >
        Why {label}?
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-20 w-64 p-3 rounded-lg border border-border bg-card shadow-lg text-[11px] text-muted-foreground leading-relaxed">
          <p className="font-semibold text-foreground mb-1">Why this range?</p>
          <p>
            Skeldir selects the date range that maximizes statistical confidence
            while covering enough business cycles for meaningful comparison.
            Shorter ranges increase recency but widen confidence intervals.
            Longer ranges narrow intervals but may include stale patterns.
          </p>
        </div>
      )}
    </span>
  );
};

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

const Header: React.FC<{
  selectedRange: string;
  onRangeChange: (range: string) => void;
  channelCount: number;
  dateLabel?: string;
}> = ({ selectedRange, onRangeChange, channelCount, dateLabel }) => (
  <div className="flex items-center justify-between flex-wrap gap-3">
    <div className="flex items-center gap-3">
      <h1 className="text-lg font-semibold text-foreground tracking-tight">
        ATLAS Matrix
      </h1>
      {channelCount > 0 && (
        <span className="px-2 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground">
          {channelCount} channels x 5 metrics
        </span>
      )}
      {dateLabel && <WhyThisRange label={dateLabel} />}
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
                : 'bg-card text-muted-foreground hover:text-foreground hover:bg-muted/50',
            )}
          >
            {range.replace('Last ', '')}
          </button>
        ))}
      </div>
      {/* Export button */}
      <button className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
        </svg>
        Export
      </button>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Last Updated Footer
// ---------------------------------------------------------------------------

const LastUpdatedFooter: React.FC<{
  lastUpdated: string;
  dateLabel: string;
  channelCount: number;
}> = ({ lastUpdated, dateLabel, channelCount }) => {
  const timeAgo = formatTimeAgo(new Date(lastUpdated));
  return (
    <div className="flex items-center justify-between text-[10px] text-muted-foreground/60 font-mono px-1">
      <span className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Live · Updated {timeAgo}
      </span>
      <span>
        {dateLabel} · {channelCount} channels · ATLAS v4
      </span>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export interface A4AtlasComparisonProps {
  initialState: ChannelComparisonState;
}

export const A4AtlasComparison: React.FC<A4AtlasComparisonProps> = ({ initialState }) => {
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
        <Header
          selectedRange={selectedRange}
          onRangeChange={setSelectedRange}
          channelCount={0}
        />
        <EmptyState variant={initialState.variant} />
      </div>
    );
  }

  if (initialState.status === 'error') {
    return (
      <div className="p-6 max-w-[1440px] mx-auto">
        <Header
          selectedRange={selectedRange}
          onRangeChange={setSelectedRange}
          channelCount={0}
        />
        <ErrorState error={initialState.error} />
      </div>
    );
  }

  // ---------- READY STATE ----------

  const { data } = initialState;

  // Build overlap detector channels from ROAS confidence ranges
  const overlapChannels: OverlapChannel[] = data.channels.map((ch) => ({
    name: ch.channelName,
    color: ch.color,
    low: parseFloat(ch.confidenceRange.low.replace(/[$,]/g, '')),
    high: parseFloat(ch.confidenceRange.high.replace(/[$,]/g, '')),
    point: parseFloat(ch.roas.replace(/[$,]/g, '')),
  }));

  // Find winner for the banner
  const winner = data.channels.find((ch) => ch.isWinner);

  return (
    <div className="space-y-4 p-6 max-w-[1440px] mx-auto">
      {/* Header */}
      <Header
        selectedRange={selectedRange}
        onRangeChange={setSelectedRange}
        channelCount={data.channels.length}
        dateLabel={data.dateRange.label}
      />

      {/* Recommendation Strip */}
      {data.recommendation && (
        <RecommendationStrip
          summary={data.recommendation.summary}
          confidence={data.recommendation.confidence}
          expectedImpact={data.recommendation.expectedImpact}
        />
      )}

      {/* Winner Banner */}
      {winner && (
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-emerald-500/8 border border-emerald-500/20">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            className="text-emerald-400 flex-shrink-0"
          >
            <path
              d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z"
              fill="currentColor"
            />
          </svg>
          <div>
            <span className="text-xs font-semibold text-emerald-400">
              {winner.channelName}
            </span>
            <span className="text-xs text-muted-foreground ml-1.5">
              — clear ROAS leader.
            </span>
            {winner.winnerExplanation && (
              <span className="text-[10px] text-muted-foreground/70 ml-1.5">
                {winner.winnerExplanation}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Overlap Detector — hero SVG */}
      <OverlapDetector channels={overlapChannels} />

      {/* Metric Matrix — the dense grid */}
      <MetricMatrix channels={data.channels} />

      {/* Last Updated Footer */}
      <LastUpdatedFooter
        lastUpdated={data.lastUpdated}
        dateLabel={data.dateRange.label}
        channelCount={data.channels.length}
      />
    </div>
  );
};

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
