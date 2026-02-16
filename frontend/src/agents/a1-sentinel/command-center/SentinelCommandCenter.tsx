/**
 * A1-SENTINEL Command Center — Dense Control Room Dashboard
 *
 * Canonical structure preserved:
 *   Header (title + last-updated) → 3 MetricStrips → PriorityAlertStrip → ChannelTable
 *
 * Full state machine: loading / empty (4 variants) / error / ready
 * Silent polling: 30s dashboard, 5min channels, no flicker
 *
 * Master Skill citations:
 *   - Command Center canonical contract (Implementation Spec §II)
 *   - State machine: SkeldirComponentState with EmptyVariant
 *   - Copy: no forbidden patterns, outcome-first
 *   - Persona A: "Is anything on fire?" — everything above fold
 *   - Unforgettable element: RadarConfidenceSweep
 */

import { AlertCircle, RefreshCw, Radio, Plug, Clock, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useSentinelPolling } from '../hooks/useSentinelPolling';
import { RadarConfidenceSweep } from '../animations/RadarConfidenceSweep';
import { MetricStrip } from './MetricStrip';
import { PriorityAlertStrip } from './PriorityAlertStrip';
import { ChannelTable } from './ChannelTable';
import { type CommandCenterState, type EmptyVariant } from '../types';

// -- Empty State Copy (CLOSED vocabulary, outcome-first) --

const emptyStateContent: Record<EmptyVariant, { icon: typeof Plug; title: string; description: string; action?: string }> = {
  'no-data-yet': {
    icon: Plug,
    title: 'Connect your first data source to activate the Command Center',
    description: 'Link a platform account (Meta, Google, TikTok) to begin ingesting attribution data. The dashboard will populate within 24 hours of first sync.',
    action: 'Connect a platform',
  },
  'building-model': {
    icon: Clock,
    title: 'Attribution model requires 14 days of evidence to converge',
    description: 'Data is flowing. The Bayesian model needs a minimum observation window before producing reliable confidence intervals. Current progress is visible below.',
  },
  'no-results-filter': {
    icon: Radio,
    title: 'Active filters exclude all results',
    description: 'The current filter combination returns zero matching records. Adjust or clear filters to restore visibility.',
    action: 'Clear all filters',
  },
  'feature-locked': {
    icon: Lock,
    title: 'Command Center requires a Professional plan or above',
    description: 'Your current plan does not include access to the attribution dashboard. Upgrade to view real-time confidence-scored channel performance.',
    action: 'View plan options',
  },
};

// -- Main Component --

interface SentinelCommandCenterProps {
  /** Override state for Storybook / testing */
  initialState?: CommandCenterState;
}

export function SentinelCommandCenter({ initialState }: SentinelCommandCenterProps) {
  const polling = useSentinelPolling();
  const state = initialState ?? polling.state;

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-foreground">Command Center</h1>
          {state.status === 'ready' && (
            <RadarConfidenceSweep
              confidence={state.data.modelConfidence.score}
              isUpdating={polling.isUpdating}
              size={28}
              className="text-primary"
            />
          )}
        </div>

        {state.status === 'ready' && (
          <span className="font-mono text-xs text-muted-foreground tabular-nums" aria-live="polite">
            Updated {formatTimestamp(state.data.lastUpdated)}
          </span>
        )}
      </div>

      {/* ── State Machine Dispatch ── */}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'empty' && <EmptyState variant={state.variant} />}
      {state.status === 'error' && <ErrorState error={state.error} onRetry={polling.retry} />}
      {state.status === 'ready' && (
        <ReadyState
          data={state.data}
          channels={state.channels}
          isUpdating={polling.isUpdating}
        />
      )}
    </div>
  );
}

// -- Ready State --

function ReadyState({
  data,
  channels,
}: {
  data: Extract<CommandCenterState, { status: 'ready' }>['data'];
  channels: Extract<CommandCenterState, { status: 'ready' }>['channels'];
  isUpdating?: boolean;
}) {
  return (
    <>
      {/* 3 Metric Strips */}
      <div className="space-y-2" aria-label="Key metrics">
        <MetricStrip
          label="Total Revenue"
          value={data.totalRevenue.value}
          formattedValue={`$${data.totalRevenue.value.toLocaleString()}`}
          confidence={data.totalRevenue.confidence}
          confidenceInterval={data.totalRevenue.confidenceInterval}
          trend={data.totalRevenue.trend}
        />
        <MetricStrip
          label="Active Channels"
          value={data.activeChannels.count}
          formattedValue={`${data.activeChannels.count} / ${data.activeChannels.total}`}
          confidence={data.activeChannels.healthStatus === 'healthy' ? 'high' : data.activeChannels.healthStatus === 'degraded' ? 'medium' : 'low'}
          confidenceInterval={0}
          trend="stable"
        />
        <MetricStrip
          label="Model Confidence"
          value={data.modelConfidence.score}
          formattedValue={`${data.modelConfidence.score}%`}
          confidence={data.modelConfidence.score > 80 ? 'high' : data.modelConfidence.score > 50 ? 'medium' : 'low'}
          confidenceInterval={Math.round((100 - data.modelConfidence.score) * 0.3)}
          trend={data.modelConfidence.status === 'converged' ? 'up' : 'stable'}
        />
      </div>

      {/* Priority Actions */}
      <div>
        <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
          Priority Actions
        </h2>
        <PriorityAlertStrip actions={data.priorityActions} />
      </div>

      {/* Channel Performance Table */}
      <div>
        <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
          Channel Performance
        </h2>
        <ChannelTable channels={channels} />
      </div>
    </>
  );
}

// -- Loading State --

function LoadingState() {
  return (
    <div aria-busy="true" aria-label="Dashboard data syncing">
      <div className="space-y-2 mb-4">
        <MetricStrip label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
        <MetricStrip label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
        <MetricStrip label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
      </div>
      <div className="mb-4">
        <Skeleton className="h-3 w-24 mb-2" />
        <PriorityAlertStrip actions={[]} loading />
      </div>
      <div>
        <Skeleton className="h-3 w-32 mb-2" />
        <ChannelTable channels={[]} loading />
      </div>
    </div>
  );
}

// -- Empty State --

function EmptyState({ variant }: { variant: EmptyVariant }) {
  const content = emptyStateContent[variant];
  const Icon = content.icon;

  return (
    <div className="flex flex-col items-center justify-center py-16 text-center" role="status">
      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
        <Icon className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
      </div>
      <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">
        {content.title}
      </h2>
      <p className="text-xs text-muted-foreground max-w-sm mb-4">
        {content.description}
      </p>
      {content.action && (
        <Button variant="default" size="sm">
          {content.action}
        </Button>
      )}
    </div>
  );
}

// -- Error State --

function ErrorState({
  error,
  onRetry,
}: {
  error: Extract<CommandCenterState, { status: 'error' }>['error'];
  onRetry: () => void;
}) {
  return (
    <div
      className="flex flex-col items-center justify-center py-16 text-center"
      role="alert"
      aria-live="assertive"
    >
      <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
        <AlertCircle className="h-6 w-6 text-destructive" aria-hidden="true" />
      </div>
      <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">
        {error.message}
      </h2>
      <p className="font-mono text-[10px] text-muted-foreground mb-4">
        Reference: {error.correlationId}
      </p>
      {error.retryable && (
        <Button variant="default" size="sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" aria-hidden="true" />
          Retry now
        </Button>
      )}
    </div>
  );
}

// -- Helpers --

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
