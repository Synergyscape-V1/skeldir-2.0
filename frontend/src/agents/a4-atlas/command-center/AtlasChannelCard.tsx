/**
 * A4-ATLAS Channel Performance Card — Card-Wrapped Sortable Table
 *
 * Channels as a card containing a table. Default sort: confidence ascending (low first).
 * Each row has channel color dot and confidence badge.
 */
import { useState, useMemo } from 'react';
import { ArrowUpDown, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { type ChannelPerformance, type TrendDirection, CHANNEL_COLORS, formatConfidenceLabel, type ConfidenceTier } from '../types';

type SortKey = 'channelName' | 'spend' | 'revenue' | 'roas' | 'confidence';

const trendIcon: Record<TrendDirection, typeof TrendingUp> = { up: TrendingUp, down: TrendingDown, stable: Minus };
const trendColor: Record<TrendDirection, string> = { up: 'text-verified', down: 'text-destructive', stable: 'text-muted-foreground' };
function tierOf(c: number): ConfidenceTier { return c >= 80 ? 'high' : c >= 50 ? 'medium' : 'low'; }
const tierColor: Record<ConfidenceTier, string> = { high: 'text-verified', medium: 'text-unverified', low: 'text-destructive' };

interface Props {
  channels: ChannelPerformance[];
  loading?: boolean;
}

export function AtlasChannelCard({ channels, loading }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('confidence');
  const [asc, setAsc] = useState(true);

  const sorted = useMemo(() => {
    const arr = [...channels];
    arr.sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      const cmp = typeof av === 'string' ? av.localeCompare(bv as string) : (av as number) - (bv as number);
      return asc ? cmp : -cmp;
    });
    return arr;
  }, [channels, sortKey, asc]);

  const toggle = (key: SortKey) => { if (sortKey === key) setAsc(!asc); else { setSortKey(key); setAsc(true); } };

  if (loading) {
    return (
      <Card className="p-6">
        <CardHeader className="p-0 pb-4"><Skeleton className="h-4 w-40" /></CardHeader>
        <CardContent className="p-0 space-y-3">
          {[0, 1, 2, 3, 4].map(i => <Skeleton key={i} className="h-10 w-full" />)}
        </CardContent>
      </Card>
    );
  }

  const headers: { key: SortKey; label: string; align: string }[] = [
    { key: 'channelName', label: 'Channel', align: 'text-left' },
    { key: 'spend', label: 'Spend', align: 'text-right' },
    { key: 'revenue', label: 'Revenue', align: 'text-right' },
    { key: 'roas', label: 'ROAS', align: 'text-right' },
    { key: 'confidence', label: 'Confidence', align: 'text-right' },
  ];

  return (
    <Card className="p-6">
      <CardHeader className="p-0 pb-4">
        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Channel Performance</CardTitle>
      </CardHeader>
      <CardContent className="p-0 overflow-x-auto">
        <table className="w-full text-sm" role="table">
          <thead>
            <tr className="border-b border-border">
              {headers.map(h => (
                <th key={h.key} className={cn('py-2 px-2 font-medium text-muted-foreground text-[11px] uppercase tracking-wider', h.align)}>
                  <Button variant="ghost" size="sm" className="h-auto p-0 text-[11px] font-medium hover:bg-transparent" onClick={() => toggle(h.key)}>
                    {h.label}
                    <ArrowUpDown className={cn('ml-1 h-3 w-3', sortKey === h.key ? 'text-foreground' : 'text-muted-foreground/50')} />
                  </Button>
                </th>
              ))}
              <th className="py-2 px-2 text-right text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Trend</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(ch => {
              const tier = tierOf(ch.confidence);
              const TIcon = trendIcon[ch.trend];
              return (
                <tr key={ch.channelId} className="border-b border-border/50 last:border-b-0 hover:bg-accent/30 transition-colors">
                  <td className="py-2.5 px-2">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: CHANNEL_COLORS[ch.platform] }} aria-hidden="true" />
                      <span className="text-sm text-foreground font-medium">{ch.channelName}</span>
                    </div>
                  </td>
                  <td className="py-2.5 px-2 text-right font-mono text-sm tabular-nums text-foreground">${ch.spend.toLocaleString()}</td>
                  <td className="py-2.5 px-2 text-right font-mono text-sm tabular-nums text-foreground">${ch.revenue.toLocaleString()}</td>
                  <td className="py-2.5 px-2 text-right font-mono text-sm tabular-nums text-foreground">{ch.roas.toFixed(2)}x</td>
                  <td className="py-2.5 px-2 text-right">
                    <span className={cn('font-mono text-xs tabular-nums', tierColor[tier])}
                      aria-label={formatConfidenceLabel(tier, Math.round((100 - ch.confidence) * 0.3))}>
                      {ch.confidence}%
                    </span>
                  </td>
                  <td className="py-2.5 px-2 text-right">
                    <TIcon className={cn('h-4 w-4 inline-block', trendColor[ch.trend])} aria-label={`Trend: ${ch.trend}`} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
