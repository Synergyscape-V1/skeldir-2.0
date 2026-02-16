import {
  CheckCircle, Flag, Archive, UserPlus, Download, X, Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

interface BulkActionToolbarProps {
  selectedCount: number;
  selectedTotalAmount: number;
  onMarkReviewed: () => void;
  onFlagInvestigation: () => void;
  onExcludeVariance: () => void;
  onAssignUser: () => void;
  onExport: () => void;
  onClearSelection: () => void;
  isProcessing: boolean;
}

export function BulkActionToolbar({
  selectedCount,
  selectedTotalAmount,
  onMarkReviewed,
  onFlagInvestigation,
  onExcludeVariance,
  onAssignUser,
  onExport,
  onClearSelection,
  isProcessing,
}: BulkActionToolbarProps) {
  return (
    <div className="sticky top-0 z-10 bg-blue-600 dark:bg-blue-700 border-b border-blue-700 dark:border-blue-800 shadow-lg">
      <div className="px-6 py-4 flex items-center justify-between">
        {/* Left: Selection Summary */}
        <div className="flex items-center space-x-4">
          <div className="text-white">
            <span className="font-semibold text-lg" data-testid="text-selected-count">{selectedCount}</span>
            <span className="ml-1 text-blue-100">
              transaction{selectedCount !== 1 ? 's' : ''} selected
            </span>
          </div>

          <Separator orientation="vertical" className="h-6 bg-blue-400 dark:bg-blue-500" />

          <div className="text-white">
            <span className="font-semibold" data-testid="text-selected-amount">
              ${selectedTotalAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </span>
            <span className="ml-1 text-blue-100">total amount</span>
          </div>
        </div>

        {/* Right: Action Buttons */}
        <div className="flex items-center space-x-2">
          {isProcessing ? (
            <div className="flex items-center space-x-2 text-white" data-testid="indicator-processing">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">Processing...</span>
            </div>
          ) : (
            <>
              <Button
                variant="secondary"
                size="sm"
                className="bg-white text-blue-600 border-transparent hover:bg-blue-50"
                onClick={onMarkReviewed}
                data-testid="button-mark-reviewed"
              >
                <CheckCircle />
                Mark Reviewed
              </Button>

              <Button
                variant="ghost"
                size="sm"
                className="bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-400"
                onClick={onFlagInvestigation}
                data-testid="button-flag-investigation"
              >
                <Flag />
                Flag for Investigation
              </Button>

              <Button
                variant="ghost"
                size="sm"
                className="bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-400"
                onClick={onExcludeVariance}
                data-testid="button-exclude-variance"
              >
                <Archive />
                Exclude from Variance
              </Button>

              <Button
                variant="ghost"
                size="sm"
                className="bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-400"
                onClick={onAssignUser}
                data-testid="button-assign-user"
              >
                <UserPlus />
                Assign
              </Button>

              <Separator orientation="vertical" className="h-6 bg-blue-400 dark:bg-blue-500" />

              <Button
                variant="ghost"
                size="sm"
                className="bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-400"
                onClick={onExport}
                title="Export selected transactions to CSV"
                data-testid="button-export-selected"
              >
                <Download />
                Export
              </Button>

              <Button
                variant="ghost"
                size="icon"
                className="text-white hover:bg-blue-500"
                onClick={onClearSelection}
                title="Clear selection"
                data-testid="button-clear-selection"
              >
                <X className="w-5 h-5" />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
