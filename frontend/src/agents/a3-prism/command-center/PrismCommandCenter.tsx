/**
 * A3-PRISM Command Center — Adaptive Cockpit Dashboard
 *
 * Metrics with inline ConvergenceGapBars. Priority actions. Channel table.
 * Full state machine: loading / empty / error / ready.
 */
import { AlertCircle, RefreshCw, Plug, Clock, Radio, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { usePrismPolling } from '../hooks/usePrismPolling';
import { ConvergenceMetricCard } from './ConvergenceMetricCard';
import { PrismPriorityActions } from './PrismPriorityActions';
import { PrismChannelTable } from './PrismChannelTable';
import { type CommandCenterState, type EmptyVariant } from '../types';

const empty: Record<EmptyVariant, { icon: typeof Plug; title: string; desc: string; action?: string }> = {
  'no-data-yet': { icon: Plug, title: 'Connect your first data source to activate the Command Center', desc: 'Link a platform account to begin ingesting attribution data. The dashboard populates within 24 hours.', action: 'Connect a platform' },
  'building-model': { icon: Clock, title: 'Attribution model requires 14 days of evidence to converge', desc: 'Data is flowing. The Bayesian model needs a minimum observation window.' },
  'no-results-filter': { icon: Radio, title: 'Active filters exclude all results', desc: 'Adjust or clear filters to restore visibility.', action: 'Clear all filters' },
  'feature-locked': { icon: Lock, title: 'Command Center requires a Professional plan', desc: 'Upgrade to view confidence-scored channel performance.', action: 'View plan options' },
};

interface Props { initialState?: CommandCenterState; }

export function PrismCommandCenter({ initialState }: Props) {
  const polling = usePrismPolling();
  const state = initialState ?? polling.state;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Command Center</h1>
        {state.status === 'ready' && <span className="font-mono text-xs text-muted-foreground tabular-nums" aria-live="polite">Updated {fmt(state.data.lastUpdated)}</span>}
      </div>

      {state.status === 'loading' && <LoadingView />}
      {state.status === 'empty' && <EmptyView variant={state.variant} />}
      {state.status === 'error' && <ErrorView error={state.error} onRetry={polling.retry} />}
      {state.status === 'ready' && <ReadyView data={state.data} channels={state.channels} isUpdating={polling.isUpdating} />}
    </div>
  );
}

function ReadyView({ data, channels, isUpdating }: { data: Extract<CommandCenterState, { status: 'ready' }>['data']; channels: Extract<CommandCenterState, { status: 'ready' }>['channels']; isUpdating: boolean }) {
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ConvergenceMetricCard label="Total Revenue" value={data.totalRevenue.value} formattedValue={`$${data.totalRevenue.value.toLocaleString()}`} confidence={data.totalRevenue.confidence} confidenceScore={data.totalRevenue.confidence === 'high' ? 90 : data.totalRevenue.confidence === 'medium' ? 65 : 30} confidenceInterval={data.totalRevenue.confidenceInterval} trend={data.totalRevenue.trend} isUpdating={isUpdating} />
        <ConvergenceMetricCard label="Active Channels" value={data.activeChannels.count} formattedValue={`${data.activeChannels.count} / ${data.activeChannels.total}`} confidence={data.activeChannels.healthStatus === 'healthy' ? 'high' : 'medium'} confidenceScore={data.activeChannels.healthStatus === 'healthy' ? 90 : 60} confidenceInterval={0} trend="stable" isUpdating={isUpdating} />
        <ConvergenceMetricCard label="Model Confidence" value={data.modelConfidence.score} formattedValue={`${data.modelConfidence.score}%`} confidence={data.modelConfidence.score > 80 ? 'high' : data.modelConfidence.score > 50 ? 'medium' : 'low'} confidenceScore={data.modelConfidence.score} confidenceInterval={Math.round((100 - data.modelConfidence.score) * 0.3)} trend={data.modelConfidence.status === 'converged' ? 'up' : 'stable'} isUpdating={isUpdating} />
      </div>
      <div><h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Priority Actions</h2><PrismPriorityActions actions={data.priorityActions} /></div>
      <div><h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Channel Performance</h2><PrismChannelTable channels={channels} /></div>
    </>
  );
}

function LoadingView() {
  return (<div aria-busy="true"><div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
    <ConvergenceMetricCard label="" value={0} formattedValue="" confidence="high" confidenceScore={0} confidenceInterval={0} trend="stable" loading />
    <ConvergenceMetricCard label="" value={0} formattedValue="" confidence="high" confidenceScore={0} confidenceInterval={0} trend="stable" loading />
    <ConvergenceMetricCard label="" value={0} formattedValue="" confidence="high" confidenceScore={0} confidenceInterval={0} trend="stable" loading />
  </div><Skeleton className="h-3 w-24 mb-2" /><PrismPriorityActions actions={[]} loading /><div className="mt-6"><Skeleton className="h-3 w-32 mb-2" /><PrismChannelTable channels={[]} loading /></div></div>);
}

function EmptyView({ variant }: { variant: EmptyVariant }) {
  const c = empty[variant]; const Icon = c.icon;
  return (<div className="flex flex-col items-center justify-center py-20 text-center" role="status">
    <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4"><Icon className="h-6 w-6 text-muted-foreground" /></div>
    <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">{c.title}</h2>
    <p className="text-xs text-muted-foreground max-w-sm mb-4">{c.desc}</p>
    {c.action && <Button variant="default" size="sm">{c.action}</Button>}
  </div>);
}

function ErrorView({ error, onRetry }: { error: Extract<CommandCenterState, { status: 'error' }>['error']; onRetry: () => void }) {
  return (<div className="flex flex-col items-center justify-center py-20 text-center" role="alert" aria-live="assertive">
    <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center mb-4"><AlertCircle className="h-6 w-6 text-destructive" /></div>
    <h2 className="text-sm font-medium text-foreground mb-2 max-w-md">{error.message}</h2>
    <p className="font-mono text-[10px] text-muted-foreground mb-4">Reference: {error.correlationId}</p>
    {error.retryable && <Button variant="default" size="sm" onClick={onRetry}><RefreshCw className="h-3.5 w-3.5 mr-1.5" />Retry now</Button>}
  </div>);
}

function fmt(iso: string): string { const d = new Date(iso), s = Math.floor((Date.now() - d.getTime()) / 1000); if (s < 60) return `${s}s ago`; if (s < 3600) return `${Math.floor(s / 60)}m ago`; return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
