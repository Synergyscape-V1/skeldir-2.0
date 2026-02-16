/**
 * A2-MERIDIAN Command Center — Spacious Executive Dashboard
 *
 * Large metric cards, generous whitespace, breathing horizon glow.
 * Canonical: Header → 3 Metrics → Priority Actions → Channel Table
 */

import { AlertCircle, RefreshCw, Plug, Clock, Radio, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useMeridianPolling } from '../hooks/useMeridianPolling';
import { BreathingHorizonGlow } from '../animations/BreathingHorizonGlow';
import { MetricCard } from './MetricCard';
import { PriorityActionsCard } from './PriorityActionsCard';
import { ChannelPerformanceTable } from './ChannelPerformanceTable';
import { type CommandCenterState, type EmptyVariant } from '../types';

const emptyContent: Record<EmptyVariant, { icon: typeof Plug; title: string; desc: string; action?: string }> = {
  'no-data-yet': { icon: Plug, title: 'Connect your first data source to activate the Command Center', desc: 'Link a platform account (Meta, Google, TikTok) to begin ingesting attribution data. The dashboard populates within 24 hours of first sync.', action: 'Connect a platform' },
  'building-model': { icon: Clock, title: 'Attribution model requires 14 days of evidence to converge', desc: 'Data is flowing. The Bayesian model needs a minimum observation window before producing reliable confidence intervals.' },
  'no-results-filter': { icon: Radio, title: 'Active filters exclude all results', desc: 'Adjust or clear filters to restore visibility.', action: 'Clear all filters' },
  'feature-locked': { icon: Lock, title: 'Command Center requires a Professional plan or above', desc: 'Upgrade to view real-time confidence-scored channel performance.', action: 'View plan options' },
};

interface Props { initialState?: CommandCenterState; }

export function MeridianCommandCenter({ initialState }: Props) {
  const polling = useMeridianPolling();
  const state = initialState ?? polling.state;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Command Center</h1>
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
        <ReadyView data={state.data} channels={state.channels} confidence={state.data.modelConfidence.score} isUpdating={polling.isUpdating} />
      )}
    </div>
  );
}

function ReadyView({ data, channels, confidence, isUpdating }: {
  data: Extract<CommandCenterState, { status: 'ready' }>['data'];
  channels: Extract<CommandCenterState, { status: 'ready' }>['channels'];
  confidence: number;
  isUpdating: boolean;
}) {
  return (
    <>
      {/* Metric cards with breathing glow behind */}
      <div className="relative">
        <div className="absolute inset-0 -top-4 -bottom-4 overflow-hidden rounded-xl pointer-events-none">
          <BreathingHorizonGlow confidence={confidence} isUpdating={isUpdating} className="w-full h-full" />
        </div>
        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-6" aria-label="Key metrics">
          <MetricCard label="Total Revenue" value={data.totalRevenue.value} formattedValue={`$${data.totalRevenue.value.toLocaleString()}`} confidence={data.totalRevenue.confidence} confidenceInterval={data.totalRevenue.confidenceInterval} trend={data.totalRevenue.trend} />
          <MetricCard label="Active Channels" value={data.activeChannels.count} formattedValue={`${data.activeChannels.count} / ${data.activeChannels.total}`} confidence={data.activeChannels.healthStatus === 'healthy' ? 'high' : data.activeChannels.healthStatus === 'degraded' ? 'medium' : 'low'} confidenceInterval={0} trend="stable" />
          <MetricCard label="Model Confidence" value={data.modelConfidence.score} formattedValue={`${data.modelConfidence.score}%`} confidence={data.modelConfidence.score > 80 ? 'high' : data.modelConfidence.score > 50 ? 'medium' : 'low'} confidenceInterval={Math.round((100 - data.modelConfidence.score) * 0.3)} trend={data.modelConfidence.status === 'converged' ? 'up' : 'stable'} />
        </div>
      </div>

      <PriorityActionsCard actions={data.priorityActions} />
      <ChannelPerformanceTable channels={channels} />
    </>
  );
}

function LoadingView() {
  return (
    <div aria-busy="true">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <MetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
        <MetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
        <MetricCard label="" value={0} formattedValue="" confidence="high" confidenceInterval={0} trend="stable" loading />
      </div>
      <PriorityActionsCard actions={[]} loading />
      <div className="mt-8"><ChannelPerformanceTable channels={[]} loading /></div>
    </div>
  );
}

function EmptyView({ variant }: { variant: EmptyVariant }) {
  const c = emptyContent[variant];
  const Icon = c.icon;
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center" role="status">
      <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center mb-6">
        <Icon className="h-7 w-7 text-muted-foreground" />
      </div>
      <h2 className="text-base font-medium text-foreground mb-3 max-w-lg">{c.title}</h2>
      <p className="text-sm text-muted-foreground max-w-md mb-6">{c.desc}</p>
      {c.action && <Button variant="default">{c.action}</Button>}
    </div>
  );
}

function ErrorView({ error, onRetry }: { error: Extract<CommandCenterState, { status: 'error' }>['error']; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center" role="alert" aria-live="assertive">
      <div className="w-14 h-14 rounded-full bg-destructive/10 flex items-center justify-center mb-6">
        <AlertCircle className="h-7 w-7 text-destructive" />
      </div>
      <h2 className="text-base font-medium text-foreground mb-3 max-w-lg">{error.message}</h2>
      <p className="font-mono text-[10px] text-muted-foreground mb-6">Reference: {error.correlationId}</p>
      {error.retryable && (
        <Button variant="default" onClick={onRetry}><RefreshCw className="h-4 w-4 mr-2" />Retry now</Button>
      )}
    </div>
  );
}

function fmt(iso: string): string {
  const d = new Date(iso), diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
