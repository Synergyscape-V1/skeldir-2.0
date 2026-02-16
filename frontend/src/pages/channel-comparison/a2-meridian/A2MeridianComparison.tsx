/**
 * A2-MERIDIAN: Executive Brief Channel Comparison
 *
 * Design territory: McKinsey presentation deck meets executive dashboard
 * - NARRATIVE-FIRST layout — verdict/recommendation as hero element at top
 * - Ranked channel brief cards stacked in a reading flow
 * - VerdictRing SVG gauge as the unforgettable visual centerpiece
 * - LOW density, spacious, scannable, presentation-ready
 *
 * State machine: loading | empty (4 variants) | error | ready
 * All values pre-formatted by backend (Zero Mental Math).
 * No client-side statistical calculations.
 */

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import type {
  ChannelComparisonState,
  ChannelComparisonData,
  ComparisonEmptyVariant,
  SkeldirError,
} from '@/pages/channel-comparison/shared/types';
import { VerdictRing } from './VerdictRing';
import { ChannelBriefCard } from './ChannelBriefCard';

// ---------------------------------------------------------------------------
// Date Range Presets
// ---------------------------------------------------------------------------

const DATE_RANGES = ['7 Days', '30 Days', '60 Days', '90 Days'] as const;

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

const LoadingSkeleton: React.FC = () => (
  <div className="space-y-8 animate-pulse">
    {/* Header skeleton */}
    <div className="flex items-center justify-between">
      <div className="h-8 w-64 rounded-lg bg-muted" />
      <div className="flex gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-9 w-20 rounded-full bg-muted" />
        ))}
      </div>
    </div>

    {/* Verdict hero skeleton */}
    <div className="flex flex-col items-center py-10">
      <div className="w-[200px] h-[200px] rounded-full border-[10px] border-muted" />
      <div className="mt-4 h-5 w-40 rounded bg-muted" />
      <div className="mt-2 h-4 w-64 rounded bg-muted/60" />
    </div>

    {/* Card grid skeleton */}
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-muted" />
            <div className="space-y-1.5">
              <div className="h-4 w-28 rounded bg-muted" />
              <div className="h-3 w-20 rounded bg-muted/60" />
            </div>
          </div>
          <div className="space-y-2 pt-3 border-t border-border/60">
            {Array.from({ length: 5 }).map((_, j) => (
              <div key={j} className="flex justify-between">
                <div className="h-3 w-24 rounded bg-muted/40" />
                <div className="h-3 w-16 rounded bg-muted/40" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Empty States
// ---------------------------------------------------------------------------

const EmptyState: React.FC<{ variant: ComparisonEmptyVariant }> = ({ variant }) => {
  const configs: Record<
    ComparisonEmptyVariant,
    { icon: React.ReactNode; title: string; description: string; action?: string }
  > = {
    'no-data-yet': {
      icon: (
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-muted-foreground"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" strokeLinecap="round" />
        </svg>
      ),
      title: 'Connect ad platforms to generate your executive brief.',
      description:
        'Channel comparison requires at least two connected ad platforms and a verified revenue source. Once connected, the attribution model will begin building your first brief.',
      action: 'Connect Platform',
    },
    'building-model': {
      icon: (
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-primary"
        >
          <circle cx="12" cy="12" r="10" strokeDasharray="4 4" />
          <path d="M8 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      title: 'Attribution model building \u2014 accumulating evidence.',
      description:
        'The model requires at least 14 days of data from connected channels. Your executive brief will be generated once the first model run completes.',
    },
    'insufficient-selection': {
      icon: (
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-muted-foreground"
        >
          <rect x="3" y="3" width="8" height="8" rx="2" />
          <rect x="13" y="3" width="8" height="8" rx="2" strokeDasharray="3 3" />
          <rect x="3" y="13" width="8" height="8" rx="2" strokeDasharray="3 3" />
          <rect x="13" y="13" width="8" height="8" rx="2" strokeDasharray="3 3" />
        </svg>
      ),
      title: 'Select at least two channels to generate a comparison brief.',
      description:
        'Use the channel selector to pick 2\u20134 channels. The executive brief compares relative performance and generates actionable recommendations.',
    },
    'no-results-filter': {
      icon: (
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-muted-foreground"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" strokeLinecap="round" />
          <path d="M8 8l6 6M14 8l-6 6" strokeLinecap="round" />
        </svg>
      ),
      title: 'No channels match the selected date range.',
      description:
        'Adjust the date range or clear active filters to see comparison data for available channels.',
      action: 'Clear Filters',
    },
  };

  const config = configs[variant];

  return (
    <div className="flex flex-col items-center justify-center py-24 px-8 text-center max-w-lg mx-auto">
      <div className="mb-6 opacity-50">{config.icon}</div>
      <h3 className="text-base font-semibold text-foreground mb-2">{config.title}</h3>
      <p className="text-sm text-muted-foreground leading-relaxed">{config.description}</p>
      {config.action && (
        <button className="mt-6 px-5 py-2.5 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
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
  <div className="flex flex-col items-center justify-center py-24 px-8 text-center max-w-lg mx-auto">
    <svg
      width="48"
      height="48"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className="text-red-400 mb-6"
    >
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
    <h3 className="text-base font-semibold text-foreground mb-2">
      Comparison brief temporarily unavailable.
    </h3>
    <p className="text-sm text-muted-foreground leading-relaxed mb-2">
      {error.message}
    </p>
    <p className="text-xs font-mono text-muted-foreground/60 mb-6">
      Correlation ID: {error.correlationId}
    </p>
    <div className="flex gap-3">
      {error.retryable && error.action && (
        <button
          onClick={error.action.onClick}
          className="px-5 py-2.5 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          {error.action.label}
        </button>
      )}
      <button className="px-5 py-2.5 text-sm font-medium rounded-lg border border-border text-muted-foreground hover:text-foreground transition-colors">
        Report issue #{error.correlationId}
      </button>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

const Header: React.FC<{
  selectedRange: string;
  onRangeChange: (range: string) => void;
  channelCount: number;
}> = ({ selectedRange, onRangeChange, channelCount }) => (
  <div className="flex items-center justify-between flex-wrap gap-4">
    <div>
      <h1 className="text-xl font-semibold text-foreground tracking-tight">
        Executive Brief
      </h1>
      {channelCount > 0 && (
        <p className="text-sm text-muted-foreground mt-0.5">
          {channelCount}-channel comparison \u00b7 attribution summary
        </p>
      )}
    </div>
    <div className="flex items-center gap-3">
      {/* Date range pills */}
      <div className="flex rounded-full border border-border overflow-hidden bg-muted/30">
        {DATE_RANGES.map((range) => (
          <button
            key={range}
            onClick={() => onRangeChange(range)}
            className={cn(
              'px-4 py-2 text-xs font-medium transition-colors',
              selectedRange === range
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
            )}
          >
            {range}
          </button>
        ))}
      </div>
      {/* Export button */}
      <button className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-full border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
        <svg
          width="14"
          height="14"
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
// Verdict Hero Section
// ---------------------------------------------------------------------------

const VerdictHero: React.FC<{
  data: ChannelComparisonData;
}> = ({ data }) => {
  const winner = data.channels.find((ch) => ch.isWinner);
  const recommendation = data.recommendation;

  return (
    <section className="flex flex-col items-center py-10 px-4">
      {/* VerdictRing */}
      {recommendation && (
        <VerdictRing
          confidence={recommendation.confidence}
          summary={recommendation.summary}
          expectedImpact={recommendation.expectedImpact}
        />
      )}

      {/* Winner callout */}
      {winner && (
        <div className="mt-8 flex items-center gap-3 px-6 py-3 rounded-xl bg-emerald-400/5 border border-emerald-400/20">
          <svg
            width="20"
            height="20"
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
            <span className="text-sm font-semibold text-emerald-400">
              {winner.channelName}
            </span>
            <span className="text-sm text-muted-foreground ml-2">
              \u2014 clear performance leader
            </span>
          </div>
        </div>
      )}

      {/* Winner explanation */}
      {winner?.winnerExplanation && (
        <p className="mt-3 text-xs text-muted-foreground/70 text-center max-w-md leading-relaxed">
          {winner.winnerExplanation}
        </p>
      )}

      {/* Recommendation impact banner (when no ring) */}
      {!recommendation && winner && (
        <p className="mt-4 text-sm text-muted-foreground text-center">
          Recommendation unavailable \u2014 insufficient model convergence for actionable guidance.
        </p>
      )}
    </section>
  );
};

// ---------------------------------------------------------------------------
// Last Updated Footer
// ---------------------------------------------------------------------------

const LastUpdatedFooter: React.FC<{
  lastUpdated: string;
  dateRangeLabel: string;
  channelCount: number;
}> = ({ lastUpdated, dateRangeLabel, channelCount }) => {
  const timeAgo = formatTimeAgo(new Date(lastUpdated));

  return (
    <div className="flex items-center justify-between text-[11px] text-muted-foreground/60 font-mono px-1 pt-4 border-t border-border/30">
      <span className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
        </span>
        Live \u00b7 Updated {timeAgo}
      </span>
      <span>
        {dateRangeLabel} \u00b7 {channelCount} channels
      </span>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export interface A2MeridianComparisonProps {
  initialState: ChannelComparisonState;
}

export const A2MeridianComparison: React.FC<A2MeridianComparisonProps> = ({
  initialState,
}) => {
  const [selectedRange, setSelectedRange] = useState('30 Days');

  // ---------- STATE MACHINE ----------

  if (initialState.status === 'loading') {
    return (
      <div className="space-y-6 p-8 max-w-[1200px] mx-auto">
        <LoadingSkeleton />
      </div>
    );
  }

  if (initialState.status === 'empty') {
    return (
      <div className="p-8 max-w-[1200px] mx-auto">
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
      <div className="p-8 max-w-[1200px] mx-auto">
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

  // Sort channels: winner first, then by ROAS descending (narrative hierarchy)
  const sortedChannels = [...data.channels].sort((a, b) => {
    if (a.isWinner && !b.isWinner) return -1;
    if (!a.isWinner && b.isWinner) return 1;
    // Parse ROAS for secondary sort (values are pre-formatted like "$3.87")
    const roasA = parseFloat(a.roas.replace(/[^0-9.]/g, ''));
    const roasB = parseFloat(b.roas.replace(/[^0-9.]/g, ''));
    return roasB - roasA;
  });

  return (
    <div className="space-y-6 p-8 max-w-[1200px] mx-auto">
      {/* Header */}
      <Header
        selectedRange={selectedRange}
        onRangeChange={setSelectedRange}
        channelCount={data.channels.length}
      />

      {/* Verdict Hero: Ring + Winner + Recommendation */}
      <VerdictHero data={data} />

      {/* Channel Brief Cards */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-widest mb-4">
          Channel Performance
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {sortedChannels.map((channel) => (
            <ChannelBriefCard key={channel.channelId} channel={channel} />
          ))}
        </div>
      </section>

      {/* Last Updated Footer */}
      <LastUpdatedFooter
        lastUpdated={data.lastUpdated}
        dateRangeLabel={data.dateRange.label}
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
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
