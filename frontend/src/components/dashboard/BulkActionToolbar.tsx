import { 
  CheckCircle, Flag, Archive, UserPlus, Download, X, Loader2 
} from 'lucide-react';

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
          
          <div className="h-6 w-px bg-blue-400 dark:bg-blue-500" />
          
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
              <button
                onClick={onMarkReviewed}
                className="inline-flex items-center px-3 py-2 bg-white text-blue-600 text-sm font-medium 
                           rounded-md hover-elevate active-elevate-2 transition-colors focus:outline-none focus:ring-2 
                           focus:ring-white focus:ring-offset-2 focus:ring-offset-blue-600"
                data-testid="button-mark-reviewed"
              >
                <CheckCircle className="w-4 h-4 mr-2" />
                Mark Reviewed
              </button>

              <button
                onClick={onFlagInvestigation}
                className="inline-flex items-center px-3 py-2 bg-blue-500 dark:bg-blue-600 text-white text-sm font-medium 
                           rounded-md hover-elevate active-elevate-2 transition-colors focus:outline-none focus:ring-2 
                           focus:ring-white focus:ring-offset-2 focus:ring-offset-blue-600"
                data-testid="button-flag-investigation"
              >
                <Flag className="w-4 h-4 mr-2" />
                Flag for Investigation
              </button>

              <button
                onClick={onExcludeVariance}
                className="inline-flex items-center px-3 py-2 bg-blue-500 dark:bg-blue-600 text-white text-sm font-medium 
                           rounded-md hover-elevate active-elevate-2 transition-colors focus:outline-none focus:ring-2 
                           focus:ring-white focus:ring-offset-2 focus:ring-offset-blue-600"
                data-testid="button-exclude-variance"
              >
                <Archive className="w-4 h-4 mr-2" />
                Exclude from Variance
              </button>

              <button
                onClick={onAssignUser}
                className="inline-flex items-center px-3 py-2 bg-blue-500 dark:bg-blue-600 text-white text-sm font-medium 
                           rounded-md hover-elevate active-elevate-2 transition-colors focus:outline-none focus:ring-2 
                           focus:ring-white focus:ring-offset-2 focus:ring-offset-blue-600"
                data-testid="button-assign-user"
              >
                <UserPlus className="w-4 h-4 mr-2" />
                Assign
              </button>

              <div className="h-6 w-px bg-blue-400 dark:bg-blue-500" />

              <button
                onClick={onExport}
                className="inline-flex items-center px-3 py-2 bg-blue-500 dark:bg-blue-600 text-white text-sm font-medium 
                           rounded-md hover-elevate active-elevate-2 transition-colors focus:outline-none focus:ring-2 
                           focus:ring-white focus:ring-offset-2 focus:ring-offset-blue-600"
                title="Export selected transactions to CSV"
                data-testid="button-export-selected"
              >
                <Download className="w-4 h-4 mr-2" />
                Export
              </button>

              <button
                onClick={onClearSelection}
                className="inline-flex items-center p-2 text-white hover-elevate active-elevate-2 rounded-md 
                           transition-colors focus:outline-none focus:ring-2 focus:ring-white 
                           focus:ring-offset-2 focus:ring-offset-blue-600"
                title="Clear selection"
                data-testid="button-clear-selection"
              >
                <X className="w-5 h-5" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
