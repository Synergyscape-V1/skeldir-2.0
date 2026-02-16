/**
 * A1-SENTINEL ChannelTable — Channel Performance Table
 *
 * Dense tabular view: all channels visible without scrolling.
 * Default sort: low confidence first (surface problems).
 * All numbers in font-mono. Channel colors via tokens.
 *
 * Master Skill citations:
 *   - Visualization matrix: horizontal bar sorted descending for ranking
 *   - Persona A: surface problems first → sort by confidence ascending
 *   - Zero mental math: ROAS, spend, revenue pre-computed by backend
 *   - Anti-pattern: no pie/donut charts
 *   - Channel colors: deterministic, never reorder
 */

import { useState, useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus, ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  type ChannelPerformance,
  type ConfidenceTier,
  type TrendDirection,
  formatConfidenceLabel,
  CHANNEL_COLORS,
} from '../types';

interface ChannelTableProps {
  channels: ChannelPerformance[];
  loading?: boolean;
}

type SortField = 'channelName' | 'spend' | 'revenue' | 'roas' | 'confidence';
type SortDir = 'asc' | 'desc';

function confidenceTier(score: number): ConfidenceTier {
  if (score > 80) return 'high';
  if (score > 50) return 'medium';
  return 'low';
}

const trendIcons: Record<TrendDirection, { Icon: typeof TrendingUp; cls: string }> = {
  up: { Icon: TrendingUp, cls: 'text-verified' },
  down: { Icon: TrendingDown, cls: 'text-destructive' },
  stable: { Icon: Minus, cls: 'text-muted-foreground' },
};

const confidenceBadgeClass: Record<ConfidenceTier, string> = {
  high: 'bg-verified/10 text-verified',
  medium: 'bg-unverified/10 text-unverified',
  low: 'bg-destructive/10 text-destructive',
};

function formatCurrency(n: number): string {
  return `$${n.toLocaleString()}`;
}

export function ChannelTable({ channels, loading = false }: ChannelTableProps) {
  // Default sort: confidence ascending (low first → surface problems)
  const [sortField, setSortField] = useState<SortField>('confidence');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const sorted = useMemo(() => {
    if (!channels.length) return [];
    return [...channels].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      const cmp = typeof aVal === 'string'
        ? (aVal as string).localeCompare(bVal as string)
        : (aVal as number) - (bVal as number);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [channels, sortField, sortDir]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir(field === 'channelName' ? 'asc' : 'desc');
    }
  };

  if (loading) {
    return (
      <div className="border border-border rounded-md overflow-hidden" aria-busy="true">
        <div className="grid grid-cols-6 gap-4 px-4 py-2 bg-muted/30 border-b border-border">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-3 w-16" />
          ))}
        </div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="grid grid-cols-6 gap-4 px-4 py-2.5 border-b border-border last:border-b-0">
            {Array.from({ length: 6 }).map((_, j) => (
              <Skeleton key={j} className="h-4 w-full" />
            ))}
          </div>
        ))}
      </div>
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
    <div className="border border-border rounded-md overflow-hidden" role="table" aria-label="Channel performance">
      {/* Header */}
      <div className="grid grid-cols-[1fr_90px_90px_70px_160px_40px] gap-2 px-4 py-2 bg-muted/30 border-b border-border text-[11px] font-medium text-muted-foreground uppercase tracking-wider" role="row">
        {headers.map((h) => (
          <div key={h.field} className={cn('flex items-center gap-1', h.align)} role="columnheader">
            <Button
              variant="ghost"
              size="sm"
              className="h-auto p-0 text-[11px] font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground"
              onClick={() => toggleSort(h.field)}
              aria-label={`Sort by ${h.label}`}
            >
              {h.label}
              {sortField === h.field && (
                <ArrowUpDown className="h-3 w-3 ml-1 text-primary" />
              )}
            </Button>
          </div>
        ))}
        <div role="columnheader" className="text-center">Trend</div>
      </div>

      {/* Body */}
      {sorted.map((ch) => {
        const tier = confidenceTier(ch.confidence);
        const { Icon: TrendIcon, cls: trendCls } = trendIcons[ch.trend];
        const channelColor = CHANNEL_COLORS[ch.platform] || 'currentColor';

        return (
          <div
            key={ch.channelId}
            className="grid grid-cols-[1fr_90px_90px_70px_160px_40px] gap-2 px-4 py-2.5 border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors duration-120"
            role="row"
          >
            {/* Channel name with color dot */}
            <div className="flex items-center gap-2" role="cell">
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: channelColor }}
                aria-hidden="true"
              />
              <span className="text-sm font-medium text-foreground truncate">
                {ch.channelName}
              </span>
            </div>

            {/* Spend */}
            <div className="font-mono text-sm text-foreground text-right tabular-nums" role="cell">
              {formatCurrency(ch.spend)}
            </div>

            {/* Revenue */}
            <div className="font-mono text-sm text-foreground text-right tabular-nums" role="cell">
              {formatCurrency(ch.revenue)}
            </div>

            {/* ROAS */}
            <div className="font-mono text-sm text-foreground text-right tabular-nums" role="cell">
              {ch.roas.toFixed(2)}
            </div>

            {/* Confidence badge */}
            <div role="cell">
              <span
                className={cn(
                  'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium',
                  confidenceBadgeClass[tier]
                )}
              >
                {formatConfidenceLabel(tier, Math.round(100 - ch.confidence) * 0.3)}
              </span>
            </div>

            {/* Trend */}
            <div className={cn('flex items-center justify-center', trendCls)} role="cell" aria-label={`Trend: ${ch.trend}`}>
              <TrendIcon className="h-3.5 w-3.5" />
            </div>
          </div>
        );
      })}
    </div>
  );
}
