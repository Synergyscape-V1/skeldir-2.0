import { 
  CheckCircle, 
  AlertTriangle, 
  Clock, 
  ChevronRight,
  TrendingUp 
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ReconciliationStatusBadge } from '@/components/ui/ReconciliationStatusBadge';

interface DataReconciliationStatusHeaderProps {
  varianceAmount: number;
  unmatchedCount: number;
  totalTransactions: number;
  matchRate: number;
  lastSyncTime: string;
  onReviewClick: () => void;
}

export function DataReconciliationStatusHeader({
  varianceAmount,
  unmatchedCount,
  totalTransactions,
  matchRate,
  lastSyncTime,
  onReviewClick,
}: DataReconciliationStatusHeaderProps) {
  const variancePercentage = ((unmatchedCount / totalTransactions) * 100).toFixed(1);

  return (
    <div className="reconciliation-status-header bg-gradient-to-b from-red-50 to-white dark:from-red-950/20 dark:to-background border-2 border-red-200 dark:border-red-800 border-l-4 border-l-red-500 dark:border-l-red-600 rounded-md p-6 shadow-alert" data-testid="reconciliation-status-header">
      {/* PRIMARY METRIC: Financial variance at 48px */}
      <div className="flex items-start justify-between mb-6 gap-6">
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 mb-2 flex-wrap">
            <p className="text-5xl font-bold text-red-700 dark:text-red-500 tabular-nums leading-none" data-testid="text-variance-amount">
              ${varianceAmount.toLocaleString('en-US', { 
                minimumFractionDigits: 2, 
                maximumFractionDigits: 2 
              })}
            </p>
            <span className="text-base font-semibold text-red-600 dark:text-red-500 flex items-center gap-1.5" data-testid="text-requires-verification">
              <AlertTriangle className="w-5 h-5" />
              Requires Verification
            </span>
          </div>

          {/* SECONDARY METRIC: Transaction context at 16px */}
          <p className="text-base text-foreground/80 font-medium mb-4" data-testid="text-transaction-context">
            {unmatchedCount.toLocaleString()} of {totalTransactions.toLocaleString()} transactions unmatched
          </p>

          {/* TERTIARY METRIC: Match rate as supporting context at 20px */}
          <div className="flex items-center gap-4 flex-wrap">
            {/* Match rate badge - 20px via ReconciliationStatusBadge */}
            <ReconciliationStatusBadge
              variant="verified"
              showIcon={true}
              data-testid="badge-match-rate"
            >
              {matchRate}% Match Rate
            </ReconciliationStatusBadge>

            {/* Variance badge - 20px via ReconciliationStatusBadge */}
            <ReconciliationStatusBadge
              variant="error"
              showIcon={true}
              data-testid="badge-variance"
            >
              {variancePercentage}% Variance
            </ReconciliationStatusBadge>

            {/* Accuracy indicator */}
            <span className="text-xs text-muted-foreground flex items-center" data-testid="text-accuracy">
              <TrendingUp className="w-3.5 h-3.5 mr-1 text-green-600 dark:text-green-500" />
              High accuracy
            </span>
          </div>
        </div>

        {/* ACTION BUTTON: Primary CTA aligned to right */}
        <Button
          onClick={onReviewClick}
          variant="destructive"
          className="shadow-md hover:shadow-lg transition-all duration-200 flex items-center gap-2 self-start"
          data-testid="button-review-discrepancies"
        >
          <span>Review Discrepancies</span>
          <ChevronRight className="w-5 h-5" />
        </Button>
      </div>

      {/* FOOTER: Last sync timestamp */}
      <div className="flex items-center text-xs text-muted-foreground border-t border-red-100 dark:border-red-900/50 pt-3" data-testid="text-last-sync">
        <Clock className="w-3.5 h-3.5 mr-1.5" />
        <span>Last reconciliation: {lastSyncTime}</span>
      </div>
    </div>
  );
}
