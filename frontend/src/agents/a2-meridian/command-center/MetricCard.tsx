/**
 * A2-MERIDIAN MetricCard — Large Executive-Style Card
 *
 * Spacious 1/3-width card with 48px display value.
 * Confidence always visible. Generous padding.
 */

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnimatedValue } from '@/hooks/use-animated-value';
import { type ConfidenceTier, type TrendDirection, formatConfidenceLabel } from '../types';

interface MetricCardProps {
  label: string;
  value: number;
  formattedValue: string;
  confidence: ConfidenceTier;
  confidenceInterval: number;
  trend: TrendDirection;
  loading?: boolean;
}

const trendConfig: Record<TrendDirection, { icon: typeof TrendingUp; cls: string; label: string }> = {
  up: { icon: TrendingUp, cls: 'text-verified', label: 'Trending up' },
  down: { icon: TrendingDown, cls: 'text-destructive', label: 'Trending down' },
  stable: { icon: Minus, cls: 'text-muted-foreground', label: 'Stable' },
};

const confidenceColor: Record<ConfidenceTier, string> = {
  high: 'text-verified',
  medium: 'text-unverified',
  low: 'text-destructive',
};

export function MetricCard({ label, value, formattedValue, confidence, confidenceInterval, trend, loading }: MetricCardProps) {
  const animated = useAnimatedValue(value, 500);
  const TrendIcon = trendConfig[trend].icon;

  if (loading) {
    return (
      <Card className="p-8" aria-busy="true">
        <CardContent className="p-0 space-y-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-12 w-32" />
          <Skeleton className="h-4 w-40" />
        </CardContent>
      </Card>
    );
  }

  const isRevenue = formattedValue.startsWith('$');
  const display = isRevenue ? `$${Math.round(animated).toLocaleString()}` : formattedValue;
  const confLabel = formatConfidenceLabel(confidence, confidenceInterval);

  return (
    <Card
      className="p-8 transition-colors duration-200"
      aria-live="polite"
      aria-label={`${label}: ${formattedValue}, ${confLabel}, ${trendConfig[trend].label}`}
    >
      <CardContent className="p-0 space-y-3">
        <p className="text-sm text-muted-foreground font-medium">{label}</p>

        <div className="flex items-end gap-3">
          <span className="font-mono text-4xl font-semibold text-foreground tabular-nums leading-none">
            {display}
          </span>
          <span className={cn('mb-1', trendConfig[trend].cls)} aria-label={trendConfig[trend].label}>
            <TrendIcon className="h-5 w-5" />
          </span>
        </div>

        <p className={cn('text-xs font-medium', confidenceColor[confidence])}>
          {confLabel}
        </p>
      </CardContent>
    </Card>
  );
}
