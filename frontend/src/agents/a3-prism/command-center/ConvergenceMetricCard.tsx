/**
 * A3-PRISM ConvergenceMetricCard — Card with inline ConvergenceGapBars
 */

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnimatedValue } from '@/hooks/use-animated-value';
import { ConvergenceGapBars } from '../animations/ConvergenceGapBars';
import { type ConfidenceTier, type TrendDirection, formatConfidenceLabel } from '../types';

interface Props {
  label: string; value: number; formattedValue: string;
  confidence: ConfidenceTier; confidenceScore: number; confidenceInterval: number;
  trend: TrendDirection; loading?: boolean; isUpdating?: boolean;
}

const trendCfg: Record<TrendDirection, { icon: typeof TrendingUp; cls: string }> = {
  up: { icon: TrendingUp, cls: 'text-verified' },
  down: { icon: TrendingDown, cls: 'text-destructive' },
  stable: { icon: Minus, cls: 'text-muted-foreground' },
};
const confColor: Record<ConfidenceTier, string> = { high: 'text-verified', medium: 'text-unverified', low: 'text-destructive' };

export function ConvergenceMetricCard({ label, value, formattedValue, confidence, confidenceScore, confidenceInterval, trend, loading, isUpdating }: Props) {
  const animated = useAnimatedValue(value, 500);
  const TIcon = trendCfg[trend].icon;

  if (loading) {
    return <Card className="p-6"><CardContent className="p-0 space-y-3"><Skeleton className="h-4 w-20" /><Skeleton className="h-8 w-28" /><Skeleton className="h-6 w-full" /><Skeleton className="h-3 w-36" /></CardContent></Card>;
  }

  const isRevenue = formattedValue.startsWith('$');
  const display = isRevenue ? `$${Math.round(animated).toLocaleString()}` : formattedValue;

  return (
    <Card className="p-6 transition-colors duration-200" aria-live="polite"
      aria-label={`${label}: ${formattedValue}, ${formatConfidenceLabel(confidence, confidenceInterval)}`}>
      <CardContent className="p-0 space-y-3">
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{label}</p>
        <div className="flex items-end gap-2">
          <span className="font-mono text-2xl font-semibold text-foreground tabular-nums">{display}</span>
          <span className={cn('mb-0.5', trendCfg[trend].cls)}><TIcon className="h-4 w-4" /></span>
        </div>
        <ConvergenceGapBars confidence={confidenceScore} isUpdating={isUpdating} width={180} height={24} />
        <p className={cn('text-[10px] font-medium', confColor[confidence])}>{formatConfidenceLabel(confidence, confidenceInterval)}</p>
      </CardContent>
    </Card>
  );
}
