/**
 * A5-FORGE: Rank-and-Reason Channel Comparison
 *
 * Design territory: Forensic ranking — courtroom evidence brief
 * - RANK-FIRST vertical list, sorted by ROAS (highest first)
 * - Progressive disclosure: collapsed verdict, expanded evidence drawers
 * - Animated RankShiftIndicator SVGs per channel
 * - Authoritative, evidence-based aesthetic
 *
 * State machine: loading | empty (4 variants) | error | ready
 * All values pre-formatted by backend (Zero Mental Math).
 * No client-side statistical calculations.
 */

import React, { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import type {
  ChannelComparisonState,
  ChannelComparisonEntry,
  ComparisonEmptyVariant,
  ConfidenceTier,
  SkeldirError,
} from '@/pages/channel-comparison/shared/types';
import { RankedChannelRow } from './RankedChannelRow';

// ---------------------------------------------------------------------------
// Date range options
// ---------------------------------------------------------------------------

const DATE_RANGES = ['Last 7 Days', 'Last 30 Days', 'Last 60 Days', 'Last 90 Days'] as const;

// ---------------------------------------------------------------------------
// Sorting utility — parse ROAS string "$3.87" to number for sort order
// ---------------------------------------------------------------------------

function parseRoas(roasStr: string): number {
  const cleaned = roasStr.replace(/[^0-9.\-]/g, '');
  return parseFloat(cleaned) || 0;
}

function sortByRoasDesc(channels: ChannelComparisonEntry[]): ChannelComparisonEntry[] {
  return [...channels].sort((a, b) => parseRoas(b.roas) - parseRoas(a.roas));
}

// ---------------------------------------------------------------------------
// Loading skeleton
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
        <div className="h-8 w-20 rounded bg-muted" />
      </div>
    </div>
    {/* Recommendation skeleton */}
    <div className="h-14 rounded-lg bg-muted/60 border border-border" />
    {/* Ranked rows skeleton */}
    {Array.from({ length: 4 }).map((_, i) => (
      <div key={i} className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border bg-card">
        <div className={cn('rounded bg-muted', i === 0 ? 'w-10 h-10' : 'w-8 h-8')} />
        <div className="w-5 h-5 rounded bg-muted" />
        <div className="h-4 w-28 rounded bg-muted/60" />
        <div className="flex-1" />
        <div className="h-5 w-14 rounded bg-muted/60" />
        <div className="h-4 w-12 rounded bg-muted/40" />
        <div className="w-5 h-5 rounded bg-muted/40" />
        <div className="w-4 h-4 rounded bg-muted/30" />
      </div>
    ))}
  </div>
);

// ---------------------------------------------------------------------------
// Empty state — contextual per variant
// ---------------------------------------------------------------------------

const EmptyState: React.FC<{ variant: ComparisonEmptyVariant }> = ({ variant }) => {
  const configs: Record<
    ComparisonEmptyVariant,
    { icon: React.ReactNode; title: string; description: string; action?: string }
  > = {
    'no-data-yet': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <path d="M12 2v4m0 12v4M2 12h4m12 0h4" strokeLinecap="round" />
          <circle cx="12" cy="12" r="3" strokeDasharray="2 2" />
        </svg>
      ),
      title: 'No channels connected yet.',
      description: 'Connect at least two ad platforms and a revenue source to begin forensic ranking.',
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
      description: 'Ranking requires at least 14 days of data from connected channels. Rankings will appear once the model converges.',
    },
    'insufficient-selection': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <rect x="3" y="5" width="18" height="4" rx="1" />
          <rect x="3" y="12" width="12" height="4" rx="1" strokeDasharray="3 3" />
          <rect x="3" y="19" width="6" height="4" rx="1" strokeDasharray="3 3" />
        </svg>
      ),
      title: 'Select at least two channels to rank.',
      description: 'Use the channel selector above to pick 2 or more channels for ranked comparison.',
    },
    'no-results-filter': {
      icon: (
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35M8 8l6 6M14 8l-6 6" strokeLinecap="round" />
        </svg>
      ),
      title: 'No channels match this date range.',
      description: 'Adjust the date range or clear filters to see ranked comparison data.',
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
// Error state
// ---------------------------------------------------------------------------

const ErrorState: React.FC<{ error: SkeldirError }> = ({ error }) => (
  <div className="flex flex-col items-center justify-center py-20 px-8 text-center">
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-red-400 mb-4">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
    <h3 className="text-sm font-semibold text-foreground mb-1">
      Ranking data temporarily unavailable.
    </h3>
    <p className="text-xs text-muted-foreground max-w-md leading-relaxed mb-1">
      {error.message}
    </p>
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
// Recommendation card (hero — at top)
// ---------------------------------------------------------------------------

const RECOMMENDATION_BADGE_STYLES: Record<ConfidenceTier, string> = {
  high: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  low: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const RECOMMENDATION_LABELS: Record<ConfidenceTier, string> = {
  high: 'High Confidence',
  medium: 'Medium Confidence',
  low: 'Low Confidence',
};

const RecommendationCard: React.FC<{
  summary: string;
  confidence: ConfidenceTier;
  expectedImpact: string;
}> = ({ summary, confidence, expectedImpact }) => (
  <div className="flex items-center gap-4 px-5 py-3.5 rounded-lg bg-primary/5 border border-primary/15">
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className="text-primary flex-shrink-0"
    >
      <path d="M9.5 2A.5.5 0 0110 2.5V5a1 1 0 001 1h2.5a.5.5 0 01.354.854l-7 7A.5.5 0 016 13.5V11a1 1 0 00-1-1H2.5a.5.5 0 01-.354-.854l7-7A.5.5 0 019.5 2z" />
      <path d="M14.5 12a.5.5 0 01.854-.354l7 7a.5.5 0 01-.354.854H19.5a1 1 0 00-1 1v2.5a.5.5 0 01-.854.354l-7-7A.5.5 0 0111 15.5V13a1 1 0 011-1h2.5z" opacity="0.5" />
    </svg>
    <div className="flex-1 min-w-0">
      <span className="text-xs font-semibold text-foreground">{summary}</span>
      <span className="text-xs text-muted-foreground ml-2">
        Expected: {expectedImpact}
      </span>
    </div>
    <span
      className={cn(
        'flex-shrink-0 px-2 py-0.5 rounded text-[10px] font-mono font-medium border',
        RECOMMENDATION_BADGE_STYLES[confidence],
      )}
    >
      {RECOMMENDATION_LABELS[confidence]}
    </span>
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
  <div className="flex items-center justify-between flex-wrap gap-3">
    <div className="flex items-center gap-3">
      <h1 className="text-lg font-semibold text-foreground tracking-tight">
        Channel Rankings
      </h1>
      {channelCount > 0 && (
        <span className="px-2 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground">
          {channelCount} channels ranked
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
// Last updated footer
// ---------------------------------------------------------------------------

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

const LastUpdatedFooter: React.FC<{ lastUpdated: string; dateRangeLabel: string; channelCount: number }> = ({
  lastUpdated,
  dateRangeLabel,
  channelCount,
}) => {
  const timeAgo = formatTimeAgo(new Date(lastUpdated));
  return (
    <div className="flex items-center justify-between text-[10px] text-muted-foreground/60 font-mono px-1 pt-2">
      <span className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Live &middot; Updated {timeAgo}
      </span>
      <span>
        {dateRangeLabel} &middot; {channelCount} channels ranked by ROAS
      </span>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component — state machine root
// ---------------------------------------------------------------------------

export interface A5ForgeComparisonProps {
  initialState: ChannelComparisonState;
}

export const A5ForgeComparison: React.FC<A5ForgeComparisonProps> = ({ initialState }) => {
  const [selectedRange, setSelectedRange] = useState('Last 30 Days');
  const [expandedChannelId, setExpandedChannelId] = useState<string | null>(null);

  // Memoize sorted channels for ready state
  const sortedChannels = useMemo(() => {
    if (initialState.status !== 'ready') return [];
    return sortByRoasDesc(initialState.data.channels);
  }, [initialState]);

  const handleToggle = (channelId: string) => {
    setExpandedChannelId((prev) => (prev === channelId ? null : channelId));
  };

  // ---------- STATE MACHINE ----------

  if (initialState.status === 'loading') {
    return (
      <div className="space-y-6 p-6 max-w-[960px] mx-auto">
        <LoadingSkeleton />
      </div>
    );
  }

  if (initialState.status === 'empty') {
    return (
      <div className="p-6 max-w-[960px] mx-auto">
        <Header selectedRange={selectedRange} onRangeChange={setSelectedRange} channelCount={0} />
        <EmptyState variant={initialState.variant} />
      </div>
    );
  }

  if (initialState.status === 'error') {
    return (
      <div className="p-6 max-w-[960px] mx-auto">
        <Header selectedRange={selectedRange} onRangeChange={setSelectedRange} channelCount={0} />
        <ErrorState error={initialState.error} />
      </div>
    );
  }

  // ---------- READY STATE ----------
  const { data } = initialState;

  return (
    <div className="space-y-4 p-6 max-w-[960px] mx-auto">
      {/* Header */}
      <Header
        selectedRange={selectedRange}
        onRangeChange={setSelectedRange}
        channelCount={data.channels.length}
      />

      {/* Recommendation card — hero position */}
      {data.recommendation && (
        <RecommendationCard
          summary={data.recommendation.summary}
          confidence={data.recommendation.confidence}
          expectedImpact={data.recommendation.expectedImpact}
        />
      )}

      {/* Ranked list */}
      <div className="space-y-2" role="list" aria-label="Channels ranked by ROAS">
        {sortedChannels.map((channel, index) => (
          <div key={channel.channelId} role="listitem">
            <RankedChannelRow
              rank={index + 1}
              channel={channel}
              isExpanded={expandedChannelId === channel.channelId}
              onToggle={() => handleToggle(channel.channelId)}
            />
          </div>
        ))}
      </div>

      {/* Last updated footer */}
      <LastUpdatedFooter
        lastUpdated={data.lastUpdated}
        dateRangeLabel={data.dateRange.label}
        channelCount={data.channels.length}
      />
    </div>
  );
};
