/**
 * Channel Performance Table — A2-MERIDIAN base + SVG platform logos
 *
 * Executive channel view with sortable columns, confidence badges,
 * trend indicators, and platform-specific SVG logos.
 *
 * Enhancement over A2 original: replaces color-dot channel indicator
 * with monochrome platform logos (theme-safe via currentColor).
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, TrendingDown, Minus, ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getChannelLogo } from '@/assets/logos/channels';
import {
  type ChannelPerformance,
  type ConfidenceTier,
  formatConfidenceLabel,
} from './types';

interface Props {
  channels: ChannelPerformance[];
  loading?: boolean;
}

type SortField = 'channelName' | 'spend' | 'revenue' | 'roas' | 'confidence';

function tier(score: number): ConfidenceTier {
  return score > 80 ? 'high' : score > 50 ? 'medium' : 'low';
}

const trendIcon = { up: TrendingUp, down: TrendingDown, stable: Minus } as const;
const trendCls = { up: 'text-verified', down: 'text-destructive', stable: 'text-muted-foreground' } as const;
const confCls: Record<ConfidenceTier, string> = {
  high: 'bg-verified/10 text-verified',
  medium: 'bg-unverified/10 text-unverified',
  low: 'bg-destructive/10 text-destructive',
};

export function ChannelPerformanceTable({ channels, loading }: Props) {
  const [sortField, setSortField] = useState<SortField>('confidence');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const navigate = useNavigate();

  const sorted = useMemo(() => {
    if (!channels.length) return [];
    return [...channels].sort((a, b) => {
      const av = a[sortField], bv = b[sortField];
      const cmp = typeof av === 'string'
        ? (av as string).localeCompare(bv as string)
        : (av as number) - (bv as number);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [channels, sortField, sortDir]);

  const toggle = (f: SortField) => {
    if (sortField === f) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(f); setSortDir(f === 'channelName' ? 'asc' : 'desc'); }
  };

  if (loading) {
    return (
      <Card className="p-6" aria-busy="true">
        <CardHeader className="p-0 pb-4"><Skeleton className="h-4 w-40" /></CardHeader>
        <CardContent className="p-0 space-y-3">
          {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-10 w-full" />)}
        </CardContent>
      </Card>
    );
  }

  const headers: { field: SortField; label: string; align?: string }[] = [
    { field: 'channelName', label: 'Channel' },
    { field: 'spend', label: 'Spend', align: 'text-right' },
    { field: 'revenue', label: 'Revenue', align: 'text-right' },
    { field: 'roas', label: 'ROAS', align: 'text-right' },
    { field: 'confidence', label: 'Confidence' },
  ];

  return (
    <Card className="p-6">
      <CardHeader className="p-0 pb-4">
        <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Channel Performance
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="border border-border rounded-md overflow-hidden" role="table" aria-label="Channel performance">
          {/* Header row */}
          <div
            className="grid grid-cols-[1fr_90px_100px_70px_160px_40px] gap-2 px-4 py-2.5 bg-muted/30 border-b border-border"
            role="row"
          >
            {headers.map(h => (
              <div key={h.field} className={cn('flex items-center gap-1', h.align)} role="columnheader">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 text-[11px] font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground"
                  onClick={() => toggle(h.field)}
                >
                  {h.label}
                  {sortField === h.field && <ArrowUpDown className="h-3 w-3 ml-1 text-primary" />}
                </Button>
              </div>
            ))}
            <div role="columnheader" className="text-[11px] font-medium text-muted-foreground uppercase text-center">
              Trend
            </div>
          </div>

          {/* Data rows */}
          {sorted.map(ch => {
            const t = tier(ch.confidence);
            const TIcon = trendIcon[ch.trend];
            const Logo = getChannelLogo(ch.platform);

            return (
              <div
                key={ch.channelId}
                className="grid grid-cols-[1fr_90px_100px_70px_160px_40px] gap-2 px-4 py-3 border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors duration-200 cursor-pointer group"
                role="row"
                tabIndex={0}
                aria-label={`View ${ch.channelName} channel analysis`}
                onClick={() => navigate(`/channels/${ch.channelId}`)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate(`/channels/${ch.channelId}`); }}
              >
                {/* Channel name with platform logo */}
                <div className="flex items-center gap-2.5" role="cell">
                  <Logo size={18} className="text-muted-foreground flex-shrink-0" />
                  <span className="text-sm font-medium text-foreground truncate group-hover:text-primary transition-colors">{ch.channelName}</span>
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="opacity-0 group-hover:opacity-60 transition-opacity text-primary flex-shrink-0" aria-hidden="true"><path d="M2 5h6M5.5 2.5L8 5l-2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </div>

                {/* Spend */}
                <div className="font-mono text-sm text-foreground text-right tabular-nums" role="cell">
                  ${ch.spend.toLocaleString()}
                </div>

                {/* Revenue */}
                <div className="font-mono text-sm text-foreground text-right tabular-nums" role="cell">
                  ${ch.revenue.toLocaleString()}
                </div>

                {/* ROAS */}
                <div className="font-mono text-sm text-foreground text-right tabular-nums" role="cell">
                  {ch.roas.toFixed(2)}
                </div>

                {/* Confidence badge */}
                <div role="cell">
                  <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium', confCls[t])}>
                    {formatConfidenceLabel(t, Math.round((100 - ch.confidence) * 0.3))}
                  </span>
                </div>

                {/* Trend icon */}
                <div className={cn('flex items-center justify-center', trendCls[ch.trend])} role="cell">
                  <TIcon className="h-3.5 w-3.5" />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
