/**
 * A1-SENTINEL MetricStrip — Compact Horizontal Metric Card
 *
 * Dense control-room density: value + label + confidence + trend in a
 * single horizontal strip. Maximum information, minimum vertical space.
 *
 * Master Skill citations:
 *   - Typography: ALL numbers in IBM Plex Mono (font-mono)
 *   - Confidence copy: CLOSED vocabulary via formatConfidenceLabel
 *   - Zero mental math: trend direction + magnitude pre-computed
 *   - Persona A: confidence MUST be visible without hover
 */

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnimatedValue } from '@/hooks/use-animated-value';
import {
  type ConfidenceTier,
  type TrendDirection,
  formatConfidenceLabel,
} from '../types';

interface MetricStripProps {
  label: string;
  value: number;
  formattedValue: string;
  confidence: ConfidenceTier;
  confidenceInterval: number;
  trend: TrendDirection;
  loading?: boolean;
}

const trendConfig: Record<TrendDirection, { icon: typeof TrendingUp; className: string; label: string }> = {
  up: { icon: TrendingUp, className: 'text-verified', label: 'Trending up' },
  down: { icon: TrendingDown, className: 'text-destructive', label: 'Trending down' },
  stable: { icon: Minus, className: 'text-muted-foreground', label: 'Stable' },
};

const confidenceColorMap: Record<ConfidenceTier, string> = {
  high: 'bg-verified/10 text-verified border-verified/20',
  medium: 'bg-unverified/10 text-unverified border-unverified/20',
  low: 'bg-destructive/10 text-destructive border-destructive/20',
};

export function MetricStrip({
  label,
  value,
  formattedValue,
  confidence,
  confidenceInterval,
  trend,
  loading = false,
}: MetricStripProps) {
  const animatedValue = useAnimatedValue(value, 500);
  const TrendIcon = trendConfig[trend].icon;

  if (loading) {
    return (
      <div className="flex items-center gap-4 px-4 py-3 rounded-md border border-border bg-card" aria-busy="true">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-4" />
      </div>
    );
  }

  const confidenceLabel = formatConfidenceLabel(confidence, confidenceInterval);

  // Build the display value using animated number
  // For currency: keep the prefix from formattedValue, animate the number
  const isRevenue = formattedValue.startsWith('$');
  const displayValue = isRevenue
    ? `$${Math.round(animatedValue).toLocaleString()}`
    : formattedValue;

  return (
    <div
      className="flex items-center gap-4 px-4 py-3 rounded-md border border-border bg-card transition-colors duration-200"
      aria-live="polite"
      aria-label={`${label}: ${formattedValue}, ${confidenceLabel}, ${trendConfig[trend].label}`}
    >
      {/* Label */}
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap min-w-[100px]">
        {label}
      </span>

      {/* Value — font-mono per Master Skill mandate */}
      <span className="font-mono text-lg font-semibold text-foreground tabular-nums min-w-[90px]">
        {displayValue}
      </span>

      {/* Confidence badge — always visible per Persona A */}
      <span
        className={cn(
          'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border whitespace-nowrap',
          confidenceColorMap[confidence]
        )}
      >
        {confidenceLabel}
      </span>

      {/* Trend arrow */}
      <span className={cn('flex-shrink-0', trendConfig[trend].className)} aria-label={trendConfig[trend].label}>
        <TrendIcon className="h-4 w-4" />
      </span>
    </div>
  );
}
