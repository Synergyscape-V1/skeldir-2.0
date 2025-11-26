import { useState, useRef, useCallback, useMemo } from 'react';
import { 
  ChevronDown, 
  ChevronUp, 
  Clock, 
  DollarSign,
  RefreshCw,
  WifiOff,
  Download,
  FileDown,
  CheckSquare,
  Square,
  Plus,
  ChevronRight,
  X
} from 'lucide-react';
import { ReconciliationStatusIcon, DataIntegritySeal, InvestigationIcon } from '@/components/icons';
import { useLocation } from 'wouter';
import { buildImplementationPortalUrl } from '@/types/navigation';
import { PlatformVarianceGridNew } from './PlatformVarianceGridNew';
import { DataReconciliationStatusHeader } from './DataReconciliationStatusHeader';
import { PlatformLogo } from '@/components/common/PlatformLogo';
import { BulkActionToolbar } from './BulkActionToolbar';
import { BulkActionModal } from './BulkActionModal';
import { useReconciliationAutoRefresh } from '@/hooks/useReconciliationAutoRefresh';
import { formatRelativeTime } from '@/utils/dateUtils';
import { exportUnmatchedTransactions } from '@/lib/csv-export';
import { useToast } from '@/hooks/use-toast';
import { apiRequest } from '@/lib/queryClient';
import { queryClient } from '@/lib/queryClient';
import type { DataReconciliationStatus as DataReconciliationStatusType, BulkActionRequest, BulkActionResponse } from '@shared/schema';

interface DataReconciliationStatusProps {
  data: DataReconciliationStatusType;
  onRefreshData: () => Promise<DataReconciliationStatusType>; // Function to fetch fresh data
}

type SeverityLevel = 'excellent' | 'good' | 'acceptable' | 'warning' | 'critical';

interface SeverityConfig {
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description: string;
}

const getSeverityLevel = (matchPercentage: number): SeverityLevel => {
  if (matchPercentage >= 98) return 'excellent';
  if (matchPercentage >= 95) return 'good';
  if (matchPercentage >= 90) return 'acceptable';
  if (matchPercentage >= 85) return 'warning';
  return 'critical';
};

const SEVERITY_CONFIG: Record<SeverityLevel, SeverityConfig> = {
  excellent: {
    color: 'text-green-600 dark:text-green-500',
    bgColor: 'bg-green-50 dark:bg-green-950/30',
    borderColor: 'border-green-500 dark:border-green-700',
    icon: () => <ReconciliationStatusIcon size={20} status="complete" />,
    label: 'Excellent',
    description: 'Near-perfect reconciliation',
  },
  good: {
    color: 'text-green-600 dark:text-green-500',
    bgColor: 'bg-green-50 dark:bg-green-950/30',
    borderColor: 'border-green-400 dark:border-green-600',
    icon: () => <ReconciliationStatusIcon size={20} status="complete" />,
    label: 'Good',
    description: 'Within acceptable variance',
  },
  acceptable: {
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-950/30',
    borderColor: 'border-blue-400 dark:border-blue-600',
    icon: () => <ReconciliationStatusIcon size={20} status="pending" />,
    label: 'Acceptable',
    description: 'Minor discrepancies detected',
  },
  warning: {
    color: 'text-amber-600 dark:text-amber-500',
    bgColor: 'bg-amber-50 dark:bg-amber-950/30',
    borderColor: 'border-amber-500 dark:border-amber-700',
    icon: () => <ReconciliationStatusIcon size={20} status="pending" />,
    label: 'Needs Attention',
    description: 'Investigate discrepancies soon',
  },
  critical: {
    color: 'text-red-600 dark:text-red-500',
    bgColor: 'bg-red-50 dark:bg-red-950/30',
    borderColor: 'border-red-500 dark:border-red-700',
    icon: () => <ReconciliationStatusIcon size={20} status="failed" />,
    label: 'Critical',
    description: 'Immediate action required',
  },
};

export function DataReconciliationStatus({
  data,
  onRefreshData,
}: DataReconciliationStatusProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [highlightedPlatform, setHighlightedPlatform] = useState<string | null>(null);
  const platformRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [isExporting, setIsExporting] = useState(false);
  const [ctaDismissed, setCtaDismissed] = useState(false);
  const [, navigate] = useLocation();
  const { toast } = useToast();
  
  // Local state for data that gets updated by auto-refresh
  const [localData, setLocalData] = useState<DataReconciliationStatusType>(data);
  
  // Bulk action state (FE-UX-029)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isActionModalOpen, setIsActionModalOpen] = useState(false);
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Auto-refresh enabled when reconciliation incomplete
  const isAutoRefreshEnabled = localData.matchPercentage < 100;

  // Refresh callback that updates local state
  const handleRefresh = useCallback(async () => {
    const freshData = await onRefreshData();
    setLocalData(freshData);
  }, [onRefreshData]);

  // Auto-refresh hook
  const {
    isRefreshing,
    lastRefreshTime,
    nextRefreshIn,
    error: refreshError,
    refreshCount,
    triggerRefresh,
    resetError,
  } = useReconciliationAutoRefresh({
    enabled: isAutoRefreshEnabled,
    intervalMs: 30000, // 30 seconds
    onRefresh: handleRefresh,
    onError: (error) => {
      console.error('Auto-refresh failed:', error);
    },
  });

  // Export handler
  const handleExport = useCallback(async (platformFilter?: string) => {
    setIsExporting(true);
    try {
      const transactionsToExport = platformFilter
        ? localData.unmatchedTransactions.filter(t => t.platform === platformFilter)
        : localData.unmatchedTransactions;

      const currentLastSyncTime = lastRefreshTime ? formatRelativeTime(lastRefreshTime) : localData.lastSyncTime;

      await exportUnmatchedTransactions(transactionsToExport, {
        matchPercentage: localData.matchPercentage,
        variance: localData.variance,
        unmatchedCount: transactionsToExport.length,
        exportTimestamp: new Date().toISOString(),
        lastSyncTime: currentLastSyncTime,
        platformFilter,
      });

      toast({
        title: 'Export Complete',
        description: `${transactionsToExport.length} transaction${transactionsToExport.length !== 1 ? 's' : ''} exported successfully`,
      });
    } catch (error) {
      console.error('Export failed:', error);
      toast({
        title: 'Export Failed',
        description: 'Failed to export transactions. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsExporting(false);
    }
  }, [localData, lastRefreshTime, toast]);
  
  const severity = getSeverityLevel(localData.matchPercentage);
  const config = SEVERITY_CONFIG[severity];
  const StatusIcon = config.icon;
  
  // Group transactions by platform
  const platformGroups = localData.unmatchedTransactions.reduce((acc, transaction) => {
    if (!acc[transaction.platform]) {
      acc[transaction.platform] = [];
    }
    acc[transaction.platform].push(transaction);
    return acc;
  }, {} as Record<string, typeof localData.unmatchedTransactions>);
  
  // Calculate summary statistics
  const totalUnmatchedRevenue = localData.unmatchedTransactions.reduce(
    (sum, t) => sum + t.amount, 
    0
  );
  
  const avgDaysPending = localData.unmatchedTransactions.length > 0
    ? localData.unmatchedTransactions.reduce((sum, t) => sum + (t.daysPending || 0), 0) / localData.unmatchedTransactions.length
    : 0;

  const handlePlatformClick = (platformId: string) => {
    if (!isExpanded) {
      setIsExpanded(true);
    }
    
    setHighlightedPlatform(platformId);
    
    setTimeout(() => {
      const element = platformRefs.current[platformId];
      if (element) {
        element.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'nearest',
          inline: 'nearest'
        });
        
        setTimeout(() => {
          setHighlightedPlatform(null);
        }, 2000);
      }
    }, isExpanded ? 0 : 350);
  };

  // Calculate relative time for last sync display
  const lastSyncRelativeTime = lastRefreshTime ? formatRelativeTime(lastRefreshTime) : localData.lastSyncTime;

  // Selection handlers (FE-UX-029)
  const handleSelectAll = useCallback((platform?: string) => {
    const transactionsToSelect = platform 
      ? platformGroups[platform] 
      : localData.unmatchedTransactions;
    
    const newSelection = new Set(selectedIds);
    const allSelected = transactionsToSelect.every(t => selectedIds.has(t.id));
    
    if (allSelected) {
      // Deselect all in this group
      transactionsToSelect.forEach(t => newSelection.delete(t.id));
    } else {
      // Select all in this group
      transactionsToSelect.forEach(t => newSelection.add(t.id));
    }
    
    setSelectedIds(newSelection);
  }, [platformGroups, localData.unmatchedTransactions, selectedIds]);

  const handleSelectTransaction = useCallback((id: string) => {
    const newSelection = new Set(selectedIds);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    setSelectedIds(newSelection);
  }, [selectedIds]);

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  // Calculate selected transactions metadata
  const selectedTransactions = useMemo(() => 
    localData.unmatchedTransactions.filter(t => selectedIds.has(t.id)), 
    [localData.unmatchedTransactions, selectedIds]
  );
  
  const selectedTotalAmount = useMemo(() => 
    selectedTransactions.reduce((sum, t) => sum + t.amount, 0),
    [selectedTransactions]
  );

  // Bulk action handlers (FE-UX-029)
  const handleBulkAction = useCallback(async (action: string, metadata?: any) => {
    setIsProcessing(true);
    setIsActionModalOpen(false);
    
    try {
      const request: BulkActionRequest = {
        transactionIds: Array.from(selectedIds),
        action: action as any,
        metadata,
      };

      const res = await apiRequest('POST', '/api/reconciliation/bulk-action', request);
      const response: BulkActionResponse = await res.json();

      if (response.success) {
        toast({
          title: 'Success',
          description: `${response.updatedCount} transaction${response.updatedCount > 1 ? 's' : ''} updated successfully`,
        });
        
        // Clear selection after successful action
        setSelectedIds(new Set());
        
        // Invalidate and refetch reconciliation data
        await queryClient.invalidateQueries({ queryKey: ['/api/reconciliation/status'] });
        
        // Refresh data to show updated statuses
        const freshData = await onRefreshData();
        setLocalData(freshData);
      } else {
        toast({
          title: 'Error',
          description: `Failed to update transactions: ${response.message}`,
          variant: 'destructive',
        });
      }

      if (response.failedTransactions.length > 0) {
        toast({
          title: 'Partial Failure',
          description: `${response.failedTransactions.length} transaction${response.failedTransactions.length > 1 ? 's' : ''} failed to update`,
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'An error occurred while processing bulk action',
        variant: 'destructive',
      });
      console.error('Bulk action error:', error);
    } finally {
      setIsProcessing(false);
    }
  }, [selectedIds, toast, onRefreshData]);

  const openActionModal = useCallback((action: string) => {
    setCurrentAction(action);
    setIsActionModalOpen(true);
  }, []);

  // Handle review discrepancies click
  const handleReviewClick = useCallback(() => {
    if (!isExpanded) {
      setIsExpanded(true);
    }
    // Scroll to discrepancy details after a brief delay
    setTimeout(() => {
      const detailsElement = document.getElementById('discrepancy-details');
      if (detailsElement) {
        detailsElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, isExpanded ? 0 : 350);
  }, [isExpanded]);

  // Calculate total transactions for the header
  const totalTransactions = localData.unmatchedCount + (localData.matchPercentage / 100 * localData.unmatchedCount / ((100 - localData.matchPercentage) / 100));

  return (
    <div 
      className="bg-card border border-card-border rounded-md shadow-sm overflow-hidden"
      data-testid="data-reconciliation-status"
    >
      <div className="p-6">
        {/* New Header with Inverted Metric Hierarchy (FE-UX-034) */}
        <DataReconciliationStatusHeader
          varianceAmount={totalUnmatchedRevenue}
          unmatchedCount={localData.unmatchedCount}
          totalTransactions={Math.round(totalTransactions)}
          matchRate={localData.matchPercentage}
          lastSyncTime={lastSyncRelativeTime}
          onReviewClick={handleReviewClick}
        />

        {/* Export and Status Indicators */}
        <div className="mt-6 flex flex-col gap-4">
          {/* Export Button Row */}
          {localData.unmatchedCount > 0 && (
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div 
                  className={`inline-flex items-center space-x-2 px-4 py-2 ${config.bgColor} 
                              rounded-full border-2 ${config.borderColor}`}
                  data-testid="badge-severity"
                >
                  <StatusIcon className={`w-5 h-5 ${config.color}`} aria-hidden="true" />
                  <span className={`text-sm font-semibold ${config.color}`}>
                    {config.label}
                  </span>
                </div>
              </div>

              <button
                onClick={() => handleExport()}
                disabled={isExporting}
                className="inline-flex items-center px-4 py-2 border-2 border-border rounded-md 
                           text-sm font-medium text-foreground bg-card hover-elevate active-elevate-2
                           disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                aria-label="Export unmatched transactions to CSV"
                data-testid="button-export-csv"
              >
                {isExporting ? (
                  <>
                    <ReconciliationStatusIcon size={16} status="processing" aria-label="Exporting" className="mr-2" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    Export CSV
                  </>
                )}
              </button>
            </div>
          )}

          {/* Auto-Refresh Status Bar */}
          <div className="pt-4 border-t border-border">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              {/* Left: Refresh Status */}
              <div className="flex items-center space-x-3">
                {/* Refresh Status Icon */}
                {isRefreshing ? (
                  <ReconciliationStatusIcon size={16} status="processing" aria-label="Refreshing" data-testid="icon-refreshing" />
                ) : refreshError ? (
                  <WifiOff className="w-4 h-4 text-red-600 dark:text-red-500" data-testid="icon-refresh-error" />
                ) : isAutoRefreshEnabled ? (
                  <div className="relative" data-testid="indicator-auto-refresh-enabled">
                    <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse" />
                    <div className="absolute inset-0 w-2.5 h-2.5 bg-blue-500 rounded-full animate-ping opacity-75" />
                  </div>
                ) : (
                  <ReconciliationStatusIcon size={16} status="complete" aria-label="Reconciliation success" data-testid="icon-reconciliation-success" />
                )}

                {/* Status Text */}
                <div className="flex flex-col">
                  <div className="flex items-center space-x-2 text-sm">
                    {isRefreshing ? (
                      <span className="text-blue-700 dark:text-blue-400 font-medium" data-testid="text-refresh-status">Refreshing data...</span>
                    ) : refreshError ? (
                      <span className="text-red-700 dark:text-red-500 font-medium" data-testid="text-refresh-error">Refresh failed</span>
                    ) : isAutoRefreshEnabled ? (
                      <>
                        <span className="text-foreground/80 font-medium" data-testid="text-auto-refresh-enabled">Auto-refresh enabled</span>
                        <span className="text-muted-foreground" data-testid="text-next-refresh-countdown">• Next update in {nextRefreshIn}s</span>
                      </>
                    ) : (
                      <span className="text-green-700 dark:text-green-500 font-medium" data-testid="text-all-reconciled">All transactions reconciled</span>
                    )}
                  </div>
                  
                  {/* Last Update Time */}
                  <div className="flex items-center space-x-1 text-xs text-muted-foreground mt-0.5">
                    <Clock className="w-3 h-3" />
                    <span data-testid="text-last-updated">Last updated {lastSyncRelativeTime}</span>
                    {refreshCount > 0 && (
                      <span className="text-muted-foreground/70" data-testid="text-refresh-count">• {refreshCount} updates this session</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Right: Manual Refresh Button */}
              <button
                onClick={() => triggerRefresh()}
                disabled={isRefreshing}
                className={`flex items-center justify-center space-x-2 px-4 py-2 rounded-md text-sm font-medium 
                           transition-all duration-200 border-2 min-w-[140px]
                           ${isRefreshing 
                             ? 'bg-muted text-muted-foreground border-border cursor-not-allowed'
                             : 'bg-card text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800 hover-elevate active-elevate-2'
                           }`}
                aria-label="Manually refresh reconciliation data"
                data-testid="button-manual-refresh"
              >
                <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span>{isRefreshing ? 'Refreshing...' : 'Refresh Now'}</span>
              </button>
            </div>

            {/* Error Alert */}
            {refreshError && (
              <div className="mt-3 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-md flex items-start justify-between" data-testid="alert-refresh-error">
                <div className="flex items-start space-x-2">
                  <WifiOff className="w-4 h-4 text-red-600 dark:text-red-500 mt-0.5 flex-shrink-0" />
                  <div className="text-sm">
                    <p className="font-medium text-red-900 dark:text-red-200">Unable to refresh data</p>
                    <p className="text-red-700 dark:text-red-400 text-xs mt-1">
                      {refreshError.message || 'Check your connection and try again'}
                    </p>
                  </div>
                </div>
                <button
                  onClick={resetError}
                  className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 text-xs font-medium"
                  data-testid="button-dismiss-error"
                >
                  Dismiss
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* PRIMARY CTA SECTION - Conditionally Rendered when variance > 5% */}
      {localData.variance > 5 && !ctaDismissed && (
        <div className="border-t border-border bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 p-6 relative" data-testid="section-primary-cta">
          {/* Dismiss button */}
          <button
            onClick={() => setCtaDismissed(true)}
            className="absolute top-4 right-4 p-1 text-muted-foreground hover:text-foreground rounded-full 
                       hover:bg-background/50 transition-colors focus:outline-none focus:ring-2 
                       focus:ring-primary focus:ring-offset-2"
            aria-label="Dismiss recommendation"
            data-testid="button-dismiss-cta"
          >
            <X className="w-4 h-4" />
          </button>

          <div className="flex flex-col lg:flex-row items-start lg:items-center gap-6">
            {/* Left Section: Icon + Message */}
            <div className="flex items-start space-x-4 flex-1">
              {/* Icon Circle */}
              <div className="flex-shrink-0 w-12 h-12 bg-primary rounded-full flex items-center justify-center shadow-lg">
                <Plus className="w-6 h-6 text-primary-foreground" strokeWidth={2.5} />
              </div>

              {/* Text Content */}
              <div className="flex-1 min-w-0">
                <h3 className="text-base font-bold text-foreground mb-1.5" data-testid="text-cta-title">
                  Improve Your Data Confidence by {Math.max(0, 98 - localData.matchPercentage)}%
                </h3>
                
                <p className="text-sm text-foreground/80 leading-relaxed mb-4 max-w-2xl" data-testid="text-cta-description">
                  You have <span className="font-semibold text-primary">{localData.unmatchedCount} unmatched transactions</span> totaling{' '}
                  <span className="font-semibold text-primary">
                    ${totalUnmatchedRevenue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </span>.
                  Connect additional payment platforms or resolve pending reconciliations to reach 98% confidence.
                </p>

                {/* Benefit Pills */}
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center space-x-1.5 px-3 py-1.5 bg-background rounded-full border border-border shadow-sm">
                    <ReconciliationStatusIcon size={16} status="complete" aria-label="Automated" className="flex-shrink-0" />
                    <span className="text-xs font-medium text-foreground/80">Automated reconciliation</span>
                  </div>
                  
                  <div className="flex items-center space-x-1.5 px-3 py-1.5 bg-background rounded-full border border-border shadow-sm">
                    <Clock className="w-4 h-4 text-primary flex-shrink-0" />
                    <span className="text-xs font-medium text-foreground/80">5-minute setup</span>
                  </div>
                  
                  <div className="flex items-center space-x-1.5 px-3 py-1.5 bg-background rounded-full border border-border shadow-sm">
                    <DataIntegritySeal size={16} confidence="high" aria-label="Secure" className="flex-shrink-0" />
                    <span className="text-xs font-medium text-foreground/80">Bank-level security</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Section: CTA Button */}
            <div className="flex-shrink-0 w-full lg:w-auto">
              <button
                onClick={() => navigate(buildImplementationPortalUrl({ action: 'connect', source: 'reconciliation' }))}
                className="w-full lg:w-auto px-6 py-3 bg-primary hover:bg-primary/90 active:bg-primary/80 
                           text-primary-foreground text-sm font-semibold rounded-md shadow-md hover:shadow-lg 
                           transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary 
                           focus:ring-offset-2 inline-flex items-center justify-center group"
                aria-label="Open Implementation Portal to connect payment platforms"
                data-testid="button-connect-platforms"
              >
                <span>Connect Platforms</span>
                <ChevronRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
              </button>
              
              {/* Secondary link */}
              <button
                onClick={() => navigate(buildImplementationPortalUrl({ tab: 'health', source: 'reconciliation' }))}
                className="w-full lg:w-auto mt-2 text-xs text-primary hover:text-primary/80 font-medium 
                           underline underline-offset-2 focus:outline-none focus:ring-2 focus:ring-primary 
                           focus:ring-offset-2 rounded px-1"
                data-testid="link-platform-health"
              >
                View platform health dashboard →
              </button>
            </div>
          </div>

          {/* Progress Indicator */}
          <div className="mt-6 pt-4 border-t border-border/50">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
              <span data-testid="text-current-confidence">Current confidence: {localData.matchPercentage}%</span>
              <span className="font-semibold text-primary" data-testid="text-target-confidence">Target: 98%</span>
            </div>
            <div className="relative h-2 bg-muted rounded-full overflow-hidden">
              <div 
                className="absolute left-0 top-0 h-full bg-gradient-to-r from-amber-500 to-primary 
                           transition-all duration-500 rounded-full"
                style={{ width: `${localData.matchPercentage}%` }}
                data-testid="progress-current"
              />
              <div 
                className="absolute top-0 h-full w-0.5 bg-green-600 dark:bg-green-500"
                style={{ left: '98%' }}
                data-testid="progress-target-marker"
              />
            </div>
          </div>
        </div>
      )}

      <div className="p-6 pt-0">
        {localData.platformVariances.length > 0 && (
          <div className="mt-4">
            <PlatformVarianceGridNew 
              platformVariances={localData.platformVariances}
              highlightedPlatform={highlightedPlatform}
              onPlatformClick={handlePlatformClick}
            />
          </div>
        )}
      </div>

      <div className="px-6 pb-6">
        {localData.unmatchedCount > 0 && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className={`mt-6 w-full md:w-auto inline-flex items-center justify-center space-x-2 px-4 py-2.5 rounded-md font-medium 
                        text-sm border-2 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2
                        ${localData.variance > 0 
                          ? `${config.color} ${config.bgColor} ${config.borderColor} hover-elevate active-elevate-2`
                          : 'text-foreground/70 bg-muted border-border hover-elevate active-elevate-2'
                        }`}
            aria-expanded={isExpanded}
            aria-controls="discrepancy-details"
            data-testid="button-view-details"
          >
            <span>
              {isExpanded ? 'Hide Transaction Details' : `View ${localData.unmatchedCount} Unmatched Transactions`}
            </span>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
        )}
      </div>

      {isExpanded && (
        <div 
          id="discrepancy-details"
          className={`border-t-2 ${config.borderColor} bg-muted/30 p-6 animate-slideDown`}
          data-testid="panel-discrepancy-details"
        >
          {/* Bulk Action Toolbar - Sticky when transactions selected */}
          {selectedIds.size > 0 && (
            <BulkActionToolbar
              selectedCount={selectedIds.size}
              selectedTotalAmount={selectedTotalAmount}
              onMarkReviewed={() => openActionModal('mark_reviewed')}
              onFlagInvestigation={() => openActionModal('flag_investigation')}
              onExcludeVariance={() => openActionModal('exclude_variance')}
              onAssignUser={() => openActionModal('assign_user')}
              onExport={() => handleExport()}
              onClearSelection={handleClearSelection}
              isProcessing={isProcessing}
            />
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-card border border-border rounded-md p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-foreground/70 uppercase tracking-wide">
                  Total Unmatched
                </span>
                <DollarSign className="w-4 h-4 text-muted-foreground" />
              </div>
              <p className="text-2xl font-bold text-foreground" data-testid="text-total-unmatched-revenue">
                ${totalUnmatchedRevenue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Requires verification
              </p>
            </div>
            
            <div className="bg-card border border-border rounded-md p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-foreground/70 uppercase tracking-wide">
                  Platforms Affected
                </span>
              </div>
              <p className="text-2xl font-bold text-foreground" data-testid="text-platforms-affected">
                {localData.platformVariances.filter(p => p.unmatchedCount > 0).length}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                of {localData.platformVariances.length} total
              </p>
            </div>
            
            <div className="bg-card border border-border rounded-md p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-foreground/70 uppercase tracking-wide">
                  Selected
                </span>
                <CheckSquare className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              </div>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400" data-testid="text-selected-count">
                {selectedIds.size}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {selectedIds.size > 0 ? `$${selectedTotalAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })} total` : 'No transactions selected'}
              </p>
            </div>
          </div>

          <div className="space-y-6">
            {Object.entries(platformGroups).map(([platform, transactions]) => {
              const platformData = localData.platformVariances.find(p => p.name === platform);
              const isHighlighted = highlightedPlatform === platformData?.id;
              
              // Platform selection state
              const platformSelectedCount = transactions.filter(t => selectedIds.has(t.id)).length;
              const allPlatformSelected = platformSelectedCount === transactions.length;
              const somePlatformSelected = platformSelectedCount > 0 && !allPlatformSelected;
              
              return (
                <div 
                  key={platform}
                  ref={(el) => {
                    if (platformData) {
                      platformRefs.current[platformData.id] = el;
                    }
                  }}
                  className={`
                    bg-card border-2 rounded-md p-5 transition-all duration-300
                    ${isHighlighted ? 'border-primary ring-4 ring-primary/20' : 'border-border'}
                  `}
                  data-testid={`panel-platform-${platformData?.id}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-border">
                    <div className="flex items-center space-x-3">
                      {/* Bulk select checkbox for platform */}
                      <button
                        onClick={() => handleSelectAll(platform)}
                        className="focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-600 rounded transition-colors hover-elevate active-elevate-2"
                        aria-label={`Select all ${platform} transactions`}
                        data-testid={`button-select-all-${platformData?.id}`}
                      >
                        {allPlatformSelected ? (
                          <CheckSquare className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                        ) : somePlatformSelected ? (
                          <Square className="w-5 h-5 text-blue-600 dark:text-blue-400 fill-blue-100 dark:fill-blue-900/30" />
                        ) : (
                          <Square className="w-5 h-5 text-muted-foreground" />
                        )}
                      </button>

                      <PlatformLogo 
                        platform={platform}
                        size="md"
                        showFallback={true}
                        className="drop-shadow-sm"
                      />
                      <div>
                        <h3 className="text-base font-bold text-foreground">
                          {platform}
                          {platformSelectedCount > 0 && (
                            <span className="ml-2 text-blue-600 dark:text-blue-400 font-medium text-sm">
                              — {platformSelectedCount} selected
                            </span>
                          )}
                        </h3>
                        <span className="text-xs text-muted-foreground">
                          {transactions.length} unmatched transaction{transactions.length !== 1 ? 's' : ''}
                        </span>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className="text-lg font-bold text-foreground">
                          ${transactions.reduce((sum, t) => sum + t.amount, 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </p>
                        {platformData && (
                          <p className="text-xs text-muted-foreground">
                            {platformData.matchPercentage}% match rate
                          </p>
                        )}
                      </div>

                      <button
                        onClick={() => handleExport(platform)}
                        disabled={isExporting}
                        className="inline-flex items-center px-3 py-1.5 border border-border rounded-md 
                                   text-xs font-medium text-foreground bg-card hover-elevate active-elevate-2
                                   disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        aria-label={`Export ${platform} transactions to CSV`}
                        data-testid={`button-export-platform-${platformData?.id}`}
                      >
                        <FileDown className="w-3.5 h-3.5 mr-1.5" />
                        Export {platform}
                      </button>
                    </div>
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-muted/50 border-b border-border">
                        <tr>
                          <th className="w-10 py-3 px-3"></th>
                          <th className="text-left py-3 px-4 text-xs font-semibold text-foreground/70 uppercase tracking-wide">
                            Transaction ID
                          </th>
                          <th className="text-left py-3 px-4 text-xs font-semibold text-foreground/70 uppercase tracking-wide">
                            Date
                          </th>
                          <th className="text-right py-3 px-4 text-xs font-semibold text-foreground/70 uppercase tracking-wide">
                            Amount
                          </th>
                          <th className="text-left py-3 px-4 text-xs font-semibold text-foreground/70 uppercase tracking-wide">
                            Type
                          </th>
                          <th className="text-left py-3 px-4 text-xs font-semibold text-foreground/70 uppercase tracking-wide">
                            Reason
                          </th>
                          <th className="text-left py-3 px-4 text-xs font-semibold text-foreground/70 uppercase tracking-wide">
                            Status
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {transactions.slice(0, 5).map((transaction) => {
                          const isSelected = selectedIds.has(transaction.id);
                          
                          return (
                            <tr 
                              key={transaction.id} 
                              className={`hover-elevate transition-colors ${
                                isSelected ? 'bg-blue-50 dark:bg-blue-950/20' : ''
                              }`}
                              data-testid={`row-transaction-${transaction.id}`}
                            >
                              {/* Selection Checkbox */}
                              <td className="py-3 px-3">
                                <button
                                  onClick={() => handleSelectTransaction(transaction.id)}
                                  className="focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-600 rounded transition-colors hover-elevate active-elevate-2"
                                  aria-label={`Select transaction ${transaction.id}`}
                                  data-testid={`button-select-transaction-${transaction.id}`}
                                >
                                  {isSelected ? (
                                    <CheckSquare className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                  ) : (
                                    <Square className="w-4 h-4 text-muted-foreground" />
                                  )}
                                </button>
                              </td>

                              <td className="py-3 px-4 font-mono text-xs text-foreground">
                                {transaction.id}
                              </td>
                              <td className="py-3 px-4 text-foreground/80 whitespace-nowrap">
                                {new Date(transaction.date).toLocaleDateString('en-US', { 
                                  month: 'short', 
                                  day: 'numeric',
                                  year: 'numeric'
                                })}
                              </td>
                              <td className="py-3 px-4 text-right font-semibold text-foreground tabular-nums">
                                ${transaction.amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                              </td>
                              <td className="py-3 px-4 text-foreground/70 text-xs capitalize">
                                {transaction.transactionType}
                              </td>
                              <td className="py-3 px-4 text-foreground/70 text-xs max-w-xs truncate">
                                {transaction.reason}
                              </td>
                              <td className="py-3 px-4">
                                <span className={`
                                  inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium
                                  ${transaction.status === 'investigating' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-800' :
                                    transaction.status === 'pending_data' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800' :
                                    transaction.status === 'variance_detected' ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800' :
                                    transaction.status === 'reviewed' ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-800' :
                                    'bg-gray-100 dark:bg-gray-900/30 text-gray-800 dark:text-gray-300 border border-gray-200 dark:border-gray-800'}
                                `}>
                                  {transaction.status.replace('_', ' ')}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  
                  {transactions.length > 5 && (
                    <div className="mt-4 pt-4 border-t border-border">
                      <button 
                        className="text-primary hover:text-primary/80 text-sm font-medium hover-elevate
                                   focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded px-2 py-1"
                        data-testid={`button-view-all-${platformData?.id}`}
                      >
                        View all {transactions.length} {platform} transactions →
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bulk Action Modal */}
      {isActionModalOpen && currentAction && (
        <BulkActionModal
          action={currentAction}
          selectedCount={selectedIds.size}
          selectedTransactions={selectedTransactions}
          onConfirm={(metadata) => handleBulkAction(currentAction, metadata)}
          onCancel={() => setIsActionModalOpen(false)}
        />
      )}
    </div>
  );
}
