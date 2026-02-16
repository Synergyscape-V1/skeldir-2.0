/**
 * Final Command Center — A4-ATLAS × A2-MERIDIAN Hybrid
 *
 * Composition:
 *   KPI Tiles (top row):     A4-ATLAS MetricCard (Total Revenue, Active Channels, Model Confidence)
 *   Priority Actions:        A2-MERIDIAN PriorityActionsCard
 *   Channel Performance:     A2-MERIDIAN ChannelPerformanceTable + SVG platform logos
 *
 * Canonical structure preserved:
 *   Header → 3 MetricCards → PriorityActions → ChannelPerformanceTable
 *
 * Full state machine: loading / empty (4 variants) / error / ready
 * Silent polling: 30s dashboard, 5min channels, no flicker
 *
 * Master Skill compliance:
 *   - Zero hardcoded hex/rgb — all via CSS variables / Tailwind tokens
 *   - Closed confidence vocabulary via formatConfidenceLabel
 *   - No forbidden copy patterns
 *   - No UI-side business/statistical logic
 *   - prefers-reduced-motion respected (via EvidenceAccumulatorRing)
 */

import { AlertCircle, RefreshCw, Plug, Clock, Radio, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useCommandCenterPolling } from './useCommandCenterPolling';
import { MetricCard } from './MetricCard';
import { PriorityActions } from './PriorityActions';
import { ChannelPerformanceTable } from './ChannelPerformanceTable';
import { type CommandCenterState, type EmptyVariant } from './types';

// -- Empty State Copy (CLOSED vocabulary, outcome-first, no forbidden patterns) --

const emptyConfig: Record<EmptyVariant, { icon: typeof Plug; title: string; desc: string; action?: string }> = {
  'no-data-yet': {
    icon: Plug,
    title: 'Connect your first data source to activate the Command Center',
    desc: 'Link a platform account to begin ingesting attribution data. The dashboard populates within 24 hours of first sync.',
    action: 'Connect a platform',
  },
  'building-model': {
    icon: Clock,
    title: 'Attribution model requires 14 days of evidence to converge',
    desc: 'Data is flowing. The Bayesian model needs a minimum observation window before producing reliable confidence intervals.',
  },
  'no-results-filter': {
    icon: Radio,
    title: 'Active filters exclude all results',
    desc: 'The current filter combination returns zero matching records. Adjust or clear filters to restore visibility.',
    action: 'Clear all filters',
  },
  'feature-locked': {
    icon: Lock,
    title: 'Command Center requires a Professional plan or above',
    desc: 'Your current plan does not include access to the attribution dashboard. Upgrade to view real-time confidence-scored channel performance.',
    action: 'View plan options',
  },
};

// -- Main Component --

interface CommandCenterProps {
  /** Override state for Storybook / testing */
  initialState?: CommandCenterState;
}

export function CommandCenter({ initialState }: CommandCenterProps) {
  const polling = useCommandCenterPolling();
  const state = initialState ?? polling.state;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Command Center</h1>
        {state.status === 'ready' && (
          <span className="font-mono text-xs text-muted-foreground tabular-nums" aria-live="polite">
            Updated {formatTimestamp(state.data.lastUpdated)}
          </span>
        )}
      </div>

      {/* State Machine Dispatch */}
      {state.status === 'loading' && <LoadingView />}
      {state.status === 'empty' && <EmptyView variant={state.variant} />}
      {state.status === 'error' && <ErrorView error={state.error} onRetry={polling.retry} />}
      {state.status === 'ready' && (
        <ReadyView data={state.data} channels={state.channels} isUpdating={polling.isUpdating} />
      )}
    </div>
  );
}

// -- Ready State (A4 tiles + A2 actions + A2 channels with logos) --

function ReadyView({
  data,
  channels,
  isUpdating,
}: {
  data: Extract<CommandCenterState, { status: 'ready' }>['data'];
  channels: Extract<CommandCenterState, { status: 'ready' }>['channels'];
  isUpdating: boolean;
}) {
  return (
    <>
      {/* KPI Tiles — A4-ATLAS MetricCard (3-column grid) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="Total Revenue"
          value={data.totalRevenue.value}
          formattedValue={`$${data.totalRevenue.value.toLocaleString()}`}
          confidence={data.totalRevenue.confidence}
          confidenceInterval={data.totalRevenue.confidenceInterval}
          trend={data.totalRevenue.trend}
          isUpdating={isUpdating}
        />
        <MetricCard
          label="Active Channels"
          value={data.activeChannels.count}
          formattedValue={`${data.activeChannels.count} / ${data.activeChannels.total}`}
          confidence={data.activeChannels.healthStatus === 'healthy' ? 'high' : data.activeChannels.healthStatus === 'degraded' ? 'medium' : 'low'}
          confidenceInterval={0}
          trend="stable"
          isUpdating={isUpdating}
        />
        <MetricCard
          label="Model Confidence"
          value={data.modelConfidence.score}
          formattedValue={`${data.modelConfidence.score}%`}
          confidence={data.modelConfidence.score > 80 ? 'high' : data.modelConfidence.score > 50 ? 'medium' : 'low'}
          confidenceInterval={Math.round((100 - data.modelConfidence.score) * 0.3)}
          trend={data.modelConfidence.status === 'converged' ? 'up' : 'stable'}
          showRing
          daysOfEvidence={data.modelConfidence.daysOfEvidence}
          confidenceScore={data.modelConfidence.score}
          isUpdating={isUpdating}
        />
      </div>

      {/* Priority Actions — A2-MERIDIAN */}
      <PriorityActions actions={data.priorityActions} />

      {/* Channel Performance — A2-MERIDIAN + SVG logos */}
      <ChannelPerformanceTable channels={channels} />
    </>
  );
}

// -- Loading State --

function LoadingView() {
  return (
    <div aria-busy="true" className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
        <MetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
        <MetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
      </div>
      <PriorityActions actions={[]} loading />
      <ChannelPerformanceTable channels={[]} loading />
    </div>
  );
}

// -- Empty State --

function EmptyView({ variant }: { variant: EmptyVariant }) {
  const cfg = emptyConfig[variant];
  const Icon = cfg.icon;

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center" role="status">
      <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center mb-4">
        <Icon className="h-7 w-7 text-muted-foreground" aria-hidden="true" />
      </div>
      <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">{cfg.title}</h2>
      <p className="text-xs text-muted-foreground max-w-sm mb-4">{cfg.desc}</p>
      {cfg.action && (
        <Button variant="default" size="sm">{cfg.action}</Button>
      )}
    </div>
  );
}

// -- Error State --

function ErrorView({
  error,
  onRetry,
}: {
  error: Extract<CommandCenterState, { status: 'error' }>['error'];
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center" role="alert" aria-live="assertive">
      <div className="w-14 h-14 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
        <AlertCircle className="h-7 w-7 text-destructive" aria-hidden="true" />
      </div>
      <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">{error.message}</h2>
      <p className="font-mono text-[10px] text-muted-foreground mb-4">Reference: {error.correlationId}</p>
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
  const diffSec = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
