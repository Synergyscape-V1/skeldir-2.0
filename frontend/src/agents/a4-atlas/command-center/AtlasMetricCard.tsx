/**
 * A4-ATLAS AtlasMetricCard — Standalone Scannable Card
 */
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAnimatedValue } from '@/hooks/use-animated-value';
import { EvidenceAccumulatorRing } from '../animations/EvidenceAccumulatorRing';
import { type ConfidenceTier, type TrendDirection, formatConfidenceLabel } from '../types';

interface Props {
  label: string; value: number; formattedValue: string;
  confidence: ConfidenceTier; confidenceInterval: number; trend: TrendDirection;
  loading?: boolean; showRing?: boolean; daysOfEvidence?: number; confidenceScore?: number; isUpdating?: boolean;
}

const tC: Record<TrendDirection, { i: typeof TrendingUp; c: string }> = {
  up: { i: TrendingUp, c: 'text-verified' }, down: { i: TrendingDown, c: 'text-destructive' }, stable: { i: Minus, c: 'text-muted-foreground' },
};
const cC: Record<ConfidenceTier, string> = { high: 'text-verified', medium: 'text-unverified', low: 'text-destructive' };

export function AtlasMetricCard({ label, value, formattedValue, confidence, confidenceInterval, trend, loading, showRing, daysOfEvidence = 0, confidenceScore = 0, isUpdating }: Props) {
  const animated = useAnimatedValue(value, 500);
  const TIcon = tC[trend].i;

  if (loading) return <Card className="p-6"><CardContent className="p-0 space-y-3"><Skeleton className="h-4 w-20" /><Skeleton className="h-10 w-28" /><Skeleton className="h-3 w-36" /></CardContent></Card>;

  const isRev = formattedValue.startsWith('$');
  const display = isRev ? `$${Math.round(animated).toLocaleString()}` : formattedValue;

  return (
    <Card className="p-6 transition-colors duration-200" aria-live="polite"
      aria-label={`${label}: ${formattedValue}, ${formatConfidenceLabel(confidence, confidenceInterval)}`}>
      <CardContent className="p-0">
        {showRing ? (
          <div className="flex items-center gap-4">
            <EvidenceAccumulatorRing daysOfEvidence={daysOfEvidence} confidence={confidenceScore} isUpdating={isUpdating} size={80} />
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{label}</p>
              <div className="flex items-end gap-2">
                <span className="font-mono text-3xl font-semibold text-foreground tabular-nums">{display}</span>
                <span className={cn('mb-0.5', tC[trend].c)}><TIcon className="h-4 w-4" /></span>
              </div>
              <p className={cn('text-[10px] font-medium', cC[confidence])}>{formatConfidenceLabel(confidence, confidenceInterval)}</p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{label}</p>
            <div className="flex items-end gap-2">
              <span className="font-mono text-3xl font-semibold text-foreground tabular-nums">{display}</span>
              <span className={cn('mb-0.5', tC[trend].c)}><TIcon className="h-4 w-4" /></span>
            </div>
            <p className={cn('text-[10px] font-medium', cC[confidence])}>{formatConfidenceLabel(confidence, confidenceInterval)}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
