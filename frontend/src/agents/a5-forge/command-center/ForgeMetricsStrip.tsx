/**
 * A5-FORGE Metrics Strip — Compressed Horizontal Metric Bar
 *
 * All three metrics in a single 48px horizontal strip.
 * Data-forward: maximum density, font-mono for all numbers.
 * Confidence tier color-coded inline.
 */
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnimatedValue } from '@/hooks/use-animated-value';
import { type ConfidenceTier, type TrendDirection, formatConfidenceLabel } from '../types';

interface MetricItem {
  label: string;
  value: number;
  formattedValue: string;
  confidence: ConfidenceTier;
  confidenceInterval: number;
  trend: TrendDirection;
}

interface Props {
  metrics: MetricItem[];
  loading?: boolean;
}

const trendIcon: Record<TrendDirection, typeof TrendingUp> = { up: TrendingUp, down: TrendingDown, stable: Minus };
const trendColor: Record<TrendDirection, string> = { up: 'text-verified', down: 'text-destructive', stable: 'text-muted-foreground' };
const tierColor: Record<ConfidenceTier, string> = { high: 'text-verified', medium: 'text-unverified', low: 'text-destructive' };

function MetricCell({ label, value, formattedValue, confidence, confidenceInterval, trend }: MetricItem) {
  const animated = useAnimatedValue(value, 500);
  const isRev = formattedValue.startsWith('$');
  const display = isRev ? `$${Math.round(animated).toLocaleString()}` : formattedValue;
  const TIcon = trendIcon[trend];

  return (
    <div
      className="flex items-center gap-3 px-4 py-2"
      aria-label={`${label}: ${formattedValue}, ${formatConfidenceLabel(confidence, confidenceInterval)}`}
      aria-live="polite"
    >
      <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider whitespace-nowrap">{label}</span>
      <span className="font-mono text-lg font-semibold text-foreground tabular-nums">{display}</span>
      <TIcon className={cn('h-3.5 w-3.5', trendColor[trend])} aria-hidden="true" />
      <span className={cn('text-[9px] font-medium whitespace-nowrap', tierColor[confidence])}>
        ±{confidenceInterval}%
      </span>
    </div>
  );
}

export function ForgeMetricsStrip({ metrics, loading }: Props) {
  if (loading) {
    return (
      <div className="flex items-center border border-border rounded-md bg-card divide-x divide-border">
        {[0, 1, 2].map(i => (
          <div key={i} className="flex items-center gap-3 px-4 py-2 flex-1">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-3 w-8" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col md:flex-row items-stretch border border-border rounded-md bg-card divide-y md:divide-y-0 md:divide-x divide-border">
      {metrics.map((m, i) => (
        <div key={i} className="flex-1">
          <MetricCell {...m} />
        </div>
      ))}
    </div>
  );
}
