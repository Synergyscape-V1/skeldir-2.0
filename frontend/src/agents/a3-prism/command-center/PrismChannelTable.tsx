/**
 * A3-PRISM ChannelTable — With inline mini ConvergenceGapBars per row
 */
import { useState, useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus, ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ConvergenceGapBars } from '../animations/ConvergenceGapBars';
import { type ChannelPerformance, type ConfidenceTier, CHANNEL_COLORS } from '../types';

type SortField = 'channelName' | 'spend' | 'revenue' | 'roas' | 'confidence';
function tier(s: number): ConfidenceTier { return s > 80 ? 'high' : s > 50 ? 'medium' : 'low'; }
const tI = { up: TrendingUp, down: TrendingDown, stable: Minus } as const;
const tC = { up: 'text-verified', down: 'text-destructive', stable: 'text-muted-foreground' } as const;

export function PrismChannelTable({ channels, loading }: { channels: ChannelPerformance[]; loading?: boolean }) {
  const [sf, setSf] = useState<SortField>('confidence');
  const [sd, setSd] = useState<'asc'|'desc'>('asc');

  const sorted = useMemo(() => {
    if (!channels.length) return [];
    return [...channels].sort((a, b) => {
      const av = a[sf], bv = b[sf];
      const cmp = typeof av === 'string' ? (av as string).localeCompare(bv as string) : (av as number) - (bv as number);
      return sd === 'asc' ? cmp : -cmp;
    });
  }, [channels, sf, sd]);

  const toggle = (f: SortField) => { if (sf === f) setSd(d => d === 'asc' ? 'desc' : 'asc'); else { setSf(f); setSd(f === 'channelName' ? 'asc' : 'desc'); } };

  if (loading) return <div className="border border-border rounded-md p-4 space-y-2" aria-busy="true">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-8 w-full" />)}</div>;

  const hdrs: { f: SortField; l: string; a?: string }[] = [
    { f: 'channelName', l: 'Channel' }, { f: 'spend', l: 'Spend', a: 'text-right' },
    { f: 'revenue', l: 'Revenue', a: 'text-right' }, { f: 'roas', l: 'ROAS', a: 'text-right' },
    { f: 'confidence', l: 'Convergence' },
  ];

  return (
    <div className="border border-border rounded-md overflow-hidden" role="table" aria-label="Channel performance">
      <div className="grid grid-cols-[1fr_80px_90px_60px_140px_36px] gap-2 px-4 py-2 bg-muted/30 border-b border-border" role="row">
        {hdrs.map(h => (
          <div key={h.f} className={cn('flex items-center gap-1', h.a)} role="columnheader">
            <Button variant="ghost" size="sm" className="h-auto p-0 text-[10px] font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground" onClick={() => toggle(h.f)}>
              {h.l}{sf === h.f && <ArrowUpDown className="h-2.5 w-2.5 ml-0.5 text-primary" />}
            </Button>
          </div>
        ))}
        <div role="columnheader" className="text-[10px] text-muted-foreground text-center">Trend</div>
      </div>
      {sorted.map(ch => {
        void tier(ch.confidence); const TIcon = tI[ch.trend];
        return (
          <div key={ch.channelId} className="grid grid-cols-[1fr_80px_90px_60px_140px_36px] gap-2 px-4 py-2 border-b border-border last:border-b-0 hover:bg-accent/50 transition-colors duration-120" role="row">
            <div className="flex items-center gap-2" role="cell">
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: CHANNEL_COLORS[ch.platform] || 'currentColor' }} />
              <span className="text-sm font-medium text-foreground truncate">{ch.channelName}</span>
            </div>
            <div className="font-mono text-sm text-right tabular-nums" role="cell">${ch.spend.toLocaleString()}</div>
            <div className="font-mono text-sm text-right tabular-nums" role="cell">${ch.revenue.toLocaleString()}</div>
            <div className="font-mono text-sm text-right tabular-nums" role="cell">{ch.roas.toFixed(2)}</div>
            <div role="cell"><ConvergenceGapBars confidence={ch.confidence} width={120} height={16} /></div>
            <div className={cn('flex items-center justify-center', tC[ch.trend])} role="cell"><TIcon className="h-3.5 w-3.5" /></div>
          </div>
        );
      })}
    </div>
  );
}
