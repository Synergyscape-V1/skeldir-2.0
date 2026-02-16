/**
 * A4-ATLAS Command Center — Card-First Scannable Grid
 *
 * Everything is a card. Metric cards top row, priority cards second row,
 * channel table card below. Full state machine: loading/empty/error/ready.
 * EvidenceAccumulatorRing appears in the Model Confidence card.
 */
import { AlertCircle, RefreshCw, Plug, Clock, Radio, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAtlasPolling } from '../hooks/useAtlasPolling';
import { AtlasMetricCard } from './AtlasMetricCard';
import { AtlasPriorityCard } from './AtlasPriorityCard';
import { AtlasChannelCard } from './AtlasChannelCard';
import { type CommandCenterState, type EmptyVariant } from '../types';

const emptyConfig: Record<EmptyVariant, { icon: typeof Plug; title: string; desc: string; action?: string }> = {
  'no-data-yet': { icon: Plug, title: 'Connect your first data source to activate the Command Center', desc: 'Link a platform account to begin ingesting attribution data. The dashboard populates within 24 hours.', action: 'Connect a platform' },
  'building-model': { icon: Clock, title: 'Attribution model requires 14 days of evidence to converge', desc: 'Data is flowing. The Bayesian model needs a minimum observation window before producing reliable estimates.' },
  'no-results-filter': { icon: Radio, title: 'Active filters exclude all results', desc: 'Adjust or clear the current filter set to restore channel visibility.', action: 'Clear all filters' },
  'feature-locked': { icon: Lock, title: 'Command Center requires a Professional plan', desc: 'Upgrade to access confidence-scored channel performance and priority actions.', action: 'View plan options' },
};

interface Props { initialState?: CommandCenterState; }

export function AtlasCommandCenter({ initialState }: Props) {
  const polling = useAtlasPolling();
  const state = initialState ?? polling.state;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Command Center</h1>
        {state.status === 'ready' && (
          <span className="font-mono text-xs text-muted-foreground tabular-nums" aria-live="polite">
            Updated {fmt(state.data.lastUpdated)}
          </span>
        )}
      </div>

      {state.status === 'loading' && <LoadingView />}
      {state.status === 'empty' && <EmptyView variant={state.variant} />}
      {state.status === 'error' && <ErrorView error={state.error} onRetry={polling.retry} />}
      {state.status === 'ready' && (
        <ReadyView data={state.data} channels={state.channels} isUpdating={polling.isUpdating} />
      )}
    </div>
  );
}

function ReadyView({
  data, channels, isUpdating,
}: {
  data: Extract<CommandCenterState, { status: 'ready' }>['data'];
  channels: Extract<CommandCenterState, { status: 'ready' }>['channels'];
  isUpdating: boolean;
}) {
  return (
    <>
      {/* Metric Cards — 3-column grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <AtlasMetricCard
          label="Total Revenue"
          value={data.totalRevenue.value}
          formattedValue={`$${data.totalRevenue.value.toLocaleString()}`}
          confidence={data.totalRevenue.confidence}
          confidenceInterval={data.totalRevenue.confidenceInterval}
          trend={data.totalRevenue.trend}
          isUpdating={isUpdating}
        />
        <AtlasMetricCard
          label="Active Channels"
          value={data.activeChannels.count}
          formattedValue={`${data.activeChannels.count} / ${data.activeChannels.total}`}
          confidence={data.activeChannels.healthStatus === 'healthy' ? 'high' : data.activeChannels.healthStatus === 'degraded' ? 'medium' : 'low'}
          confidenceInterval={0}
          trend="stable"
          isUpdating={isUpdating}
        />
        <AtlasMetricCard
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

      {/* Priority Actions */}
      <div>
        <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Priority Actions</h2>
        <AtlasPriorityCard actions={data.priorityActions} />
      </div>

      {/* Channel Performance */}
      <AtlasChannelCard channels={channels} />
    </>
  );
}

function LoadingView() {
  return (
    <div aria-busy="true" className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <AtlasMetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
        <AtlasMetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
        <AtlasMetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
      </div>
      <div>
        <Skeleton className="h-3 w-28 mb-3" />
        <AtlasPriorityCard actions={[]} loading />
      </div>
      <AtlasChannelCard channels={[]} loading />
    </div>
  );
}

function EmptyView({ variant }: { variant: EmptyVariant }) {
  const cfg = emptyConfig[variant];
  const Icon = cfg.icon;
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center" role="status">
      <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center mb-4">
        <Icon className="h-7 w-7 text-muted-foreground" />
      </div>
      <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">{cfg.title}</h2>
      <p className="text-xs text-muted-foreground max-w-sm mb-4">{cfg.desc}</p>
      {cfg.action && <Button variant="default" size="sm">{cfg.action}</Button>}
    </div>
  );
}

function ErrorView({ error, onRetry }: { error: Extract<CommandCenterState, { status: 'error' }>['error']; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center" role="alert" aria-live="assertive">
      <div className="w-14 h-14 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
        <AlertCircle className="h-7 w-7 text-destructive" />
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
