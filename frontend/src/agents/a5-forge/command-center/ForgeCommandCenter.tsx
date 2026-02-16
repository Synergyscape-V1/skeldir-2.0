/**
 * A5-FORGE Command Center — Data-Forward Tabular Dashboard
 *
 * Metrics compressed into a single horizontal strip. Channel table is the
 * primary visual element with maximum vertical space. Priority actions
 * as inline tabular rows. PulseCascadeIndicator on data refresh.
 *
 * Full state machine: loading / empty / error / ready.
 */
import { AlertCircle, RefreshCw, Plug, Clock, Radio, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useForgePolling } from '../hooks/useForgePolling';
import { PulseCascadeIndicator } from '../animations/PulseCascadeIndicator';
import { ForgeMetricsStrip } from './ForgeMetricsStrip';
import { ForgePriorityRows } from './ForgePriorityRows';
import { ForgeChannelTable } from './ForgeChannelTable';
import { type CommandCenterState, type EmptyVariant, type ConfidenceTier, type TrendDirection } from '../types';

const emptyConfig: Record<EmptyVariant, { icon: typeof Plug; title: string; desc: string; action?: string }> = {
  'no-data-yet': { icon: Plug, title: 'Connect your first data source to activate the Command Center', desc: 'Link a platform account to begin ingesting attribution data. The dashboard populates within 24 hours.', action: 'Connect a platform' },
  'building-model': { icon: Clock, title: 'Attribution model requires 14 days of evidence to converge', desc: 'Data is flowing. The Bayesian model needs a minimum observation window before producing reliable estimates.' },
  'no-results-filter': { icon: Radio, title: 'Active filters exclude all results', desc: 'Adjust or clear the current filter set to restore channel visibility.', action: 'Clear all filters' },
  'feature-locked': { icon: Lock, title: 'Command Center requires a Professional plan', desc: 'Upgrade to access confidence-scored channel performance and priority actions.', action: 'View plan options' },
};

interface Props { initialState?: CommandCenterState; }

export function ForgeCommandCenter({ initialState }: Props) {
  const polling = useForgePolling();
  const state = initialState ?? polling.state;

  return (
    <div className="space-y-4">
      {/* Header row with cascade indicator */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-foreground">Command Center</h1>
          {state.status === 'ready' && (
            <div className="flex items-center gap-3">
              <span className="font-mono text-[10px] text-muted-foreground tabular-nums" aria-live="polite">
                Updated {fmt(state.data.lastUpdated)}
              </span>
              <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                Poll #{polling.pollCount}
              </span>
            </div>
          )}
        </div>
        <PulseCascadeIndicator isUpdating={polling.isUpdating} segments={16} height={3} />
      </div>

      {state.status === 'loading' && <LoadingView />}
      {state.status === 'empty' && <EmptyView variant={state.variant} />}
      {state.status === 'error' && <ErrorView error={state.error} onRetry={polling.retry} />}
      {state.status === 'ready' && (
        <ReadyView data={state.data} channels={state.channels} />
      )}
    </div>
  );
}

function ReadyView({
  data, channels,
}: {
  data: Extract<CommandCenterState, { status: 'ready' }>['data'];
  channels: Extract<CommandCenterState, { status: 'ready' }>['channels'];
}) {
  const confTier = (s: number): ConfidenceTier => s > 80 ? 'high' : s > 50 ? 'medium' : 'low';

  const metrics = [
    {
      label: 'Revenue',
      value: data.totalRevenue.value,
      formattedValue: `$${data.totalRevenue.value.toLocaleString()}`,
      confidence: data.totalRevenue.confidence,
      confidenceInterval: data.totalRevenue.confidenceInterval,
      trend: data.totalRevenue.trend,
    },
    {
      label: 'Channels',
      value: data.activeChannels.count,
      formattedValue: `${data.activeChannels.count} / ${data.activeChannels.total}`,
      confidence: (data.activeChannels.healthStatus === 'healthy' ? 'high' : 'medium') as ConfidenceTier,
      confidenceInterval: 0,
      trend: 'stable' as TrendDirection,
    },
    {
      label: 'Model',
      value: data.modelConfidence.score,
      formattedValue: `${data.modelConfidence.score}%`,
      confidence: confTier(data.modelConfidence.score),
      confidenceInterval: Math.round((100 - data.modelConfidence.score) * 0.3),
      trend: (data.modelConfidence.status === 'converged' ? 'up' : 'stable') as TrendDirection,
    },
  ];

  return (
    <>
      {/* Compressed metrics strip */}
      <ForgeMetricsStrip metrics={metrics} />

      {/* Priority actions — inline rows */}
      {data.priorityActions.length > 0 && (
        <div>
          <h2 className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">Priority Actions</h2>
          <ForgePriorityRows actions={data.priorityActions} />
        </div>
      )}

      {/* Channel table — primary element, maximum space */}
      <div>
        <h2 className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">Channel Performance</h2>
        <ForgeChannelTable channels={channels} />
      </div>
    </>
  );
}

function LoadingView() {
  return (
    <div aria-busy="true" className="space-y-4">
      <ForgeMetricsStrip metrics={[]} loading />
      <div>
        <Skeleton className="h-3 w-24 mb-2" />
        <ForgePriorityRows actions={[]} loading />
      </div>
      <div>
        <Skeleton className="h-3 w-32 mb-2" />
        <ForgeChannelTable channels={[]} loading />
      </div>
    </div>
  );
}

function EmptyView({ variant }: { variant: EmptyVariant }) {
  const cfg = emptyConfig[variant];
  const Icon = cfg.icon;
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center" role="status">
      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">{cfg.title}</h2>
      <p className="text-xs text-muted-foreground max-w-sm mb-4">{cfg.desc}</p>
      {cfg.action && <Button variant="default" size="sm">{cfg.action}</Button>}
    </div>
  );
}

function ErrorView({ error, onRetry }: { error: Extract<CommandCenterState, { status: 'error' }>['error']; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center" role="alert" aria-live="assertive">
      <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
        <AlertCircle className="h-6 w-6 text-destructive" />
      </div>
      <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">{error.message}</h2>
      <p className="font-mono text-[10px] text-muted-foreground mb-4">Reference: {error.correlationId}</p>
      {error.retryable && (
        <Button variant="default" size="sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />Retry now
        </Button>
      )}
    </div>
  );
}

function fmt(iso: string): string {
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
