import { Clock } from 'lucide-react';
import { DataIntegritySeal, TrendIndicator } from '@/components/icons';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { RequestStatus } from '@/components/ui/request-status';
import { useVerificationSyncContext } from '@/contexts/VerificationSyncContext';
import { useAnimatedNumber } from '@/hooks/useAnimatedNumber';

/**
 * Props interface for DataConfidenceBar component
 * All metrics sourced from backend verification service
 *
 * D2-P3 State Contract: supports loading/empty/error/success via normalized status prop.
 * Non-success states delegate to RequestStatus (D1 substrate).
 */
interface DataConfidenceBarProps {
  /** Normalized state contract — drives render branch selection */
  status: 'loading' | 'error' | 'empty' | 'success';

  /** Overall data confidence score (0-100) - represents system-wide verification quality */
  overallConfidence: number;

  /** Percentage of individual transactions verified (0-100) */
  verifiedTransactionPercentage: number;

  /** Relative time string for last data sync */
  lastUpdated: string;

  /** Confidence trend direction based on recent verification changes */
  trend: 'increasing' | 'stable' | 'decreasing';

  /** Error recovery callback — required for error state, ignored otherwise */
  onRetry: () => void;

  /** Optional: Custom className for additional styling */
  className?: string;
}

/**
 * DataConfidenceBar Component
 * 
 * Bridges Revenue Overview and Data Integrity Monitor by displaying
 * overall verification confidence metrics. Provides users with immediate
 * understanding of data reliability before examining platform-level details.
 * 
 * Design Pattern: Information architecture bridge component
 * Position: Between RevenueOverview and DataIntegrityMonitor
 * 
 * @example
 * <DataConfidenceBar
 *   overallConfidence={87}
 *   verifiedTransactionPercentage={45}
 *   lastUpdated="2 minutes ago"
 *   trend="increasing"
 * />
 */
export function DataConfidenceBar({
  status,
  overallConfidence,
  verifiedTransactionPercentage,
  lastUpdated,
  trend,
  onRetry,
  className = '',
}: DataConfidenceBarProps) {
  /**
   * Confidence Level Determination
   * High: ≥85% - Green indicators, "High accuracy" label
   * Medium: 70-84% - Amber indicators, "Medium accuracy" label
   * Low: <70% - Red indicators, "Low accuracy" label
   */
  const getConfidenceLevel = (score: number): 'high' | 'medium' | 'low' => {
    if (score >= 85) return 'high';
    if (score >= 70) return 'medium';
    return 'low';
  };

  const confidenceLevel = getConfidenceLevel(overallConfidence);

  /**
   * Color Configuration by Confidence Level
   * Uses shadcn design tokens for consistency
   */
  const confidenceColors = {
    high: {
      bg: 'bg-green-50 dark:bg-green-950/30',
      border: 'border-green-200 dark:border-green-800',
      text: 'text-green-700 dark:text-green-400',
      icon: 'text-green-600 dark:text-green-500',
      badge: 'bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300',
    },
    medium: {
      bg: 'bg-amber-50 dark:bg-amber-950/30',
      border: 'border-amber-200 dark:border-amber-800',
      text: 'text-amber-700 dark:text-amber-400',
      icon: 'text-amber-600 dark:text-amber-500',
      badge: 'bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-300',
    },
    low: {
      bg: 'bg-red-50 dark:bg-red-950/30',
      border: 'border-red-200 dark:border-red-800',
      text: 'text-red-700 dark:text-red-400',
      icon: 'text-red-600 dark:text-red-500',
      badge: 'bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300',
    },
  };

  const colors = confidenceColors[confidenceLevel];

  /**
   * Trend direction mapping for TrendIndicator component
   * Maps trend prop to icon direction
   */
  const trendDirection: 'up' | 'down' | 'stable' = 
    trend === 'increasing' ? 'up' :
    trend === 'decreasing' ? 'down' :
    'stable';

  const trendColors = {
    increasing: 'text-green-600 dark:text-green-500',
    decreasing: 'text-red-600 dark:text-red-500',
    stable: 'text-muted-foreground',
  };

  const trendLabels = {
    increasing: 'Improving',
    decreasing: 'Declining',
    stable: 'Stable',
  };

  /**
   * Accuracy Label Mapping
   * User-friendly terminology for confidence levels
   */
  const accuracyLabels = {
    high: 'High accuracy',
    medium: 'Medium accuracy',
    low: 'Needs attention',
  };

  // FE-UX-021: Verification Sync Integration
  const { highlightedComponent, isAnimating } = useVerificationSyncContext();
  
  // Animate confidence percentage when verification sync is active
  const animatedConfidence = useAnimatedNumber(
    overallConfidence,
    500,
    isAnimating
  );
  
  // Animate transaction percentage when verification sync is active
  const animatedTransactionPercentage = useAnimatedNumber(
    verifiedTransactionPercentage,
    500,
    isAnimating
  );

  // Determine if should be highlighted during verification sync
  const isHighlighted = highlightedComponent === 'confidence' && isAnimating;

  // D2-P3: Non-success state branches — delegate to RequestStatus substrate
  if (status !== 'success') {
    return (
      <div
        className={`data-confidence-bar border-t border-b border-border bg-muted/30 py-4 px-6 ${className}`}
        role="status"
        aria-live="polite"
        aria-label="Data confidence bar"
        data-testid="data-confidence-bar"
        data-status={status}
      >
        <RequestStatus
          {...(status === 'error' ? {
            status: 'error' as const,
            message: 'Failed to load confidence data',
            onRetry,
            skeletonVariant: 'card' as const,
          } : status === 'empty' ? {
            status: 'empty' as const,
            message: 'No confidence data available',
            skeletonVariant: 'card' as const,
          } : {
            status: 'loading' as const,
            skeletonVariant: 'card' as const,
          })}
        />
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div
        className={`data-confidence-bar ${colors.bg} border-t ${colors.border} border-b py-4 px-6
                    transition-colors duration-300 ease-in-out
                    ${isHighlighted ? 'ring-4 ring-blue-300 ring-opacity-50 animate-pulse-once' : ''}
                    ${className}`}
        role="status"
        aria-live="polite"
        aria-label={`Data confidence: ${overallConfidence}%, trend ${trend}`}
        data-testid="data-confidence-bar"
        data-status="success"
        data-protected-zone="verification-status"
      >
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          
          {/* LEFT SECTION: Primary Confidence Metrics */}
          <div className="flex items-start lg:items-center gap-4">
            {/* Data Integrity Seal - Primary indicator */}
            <DataIntegritySeal 
              size={24}
              confidence={confidenceLevel}
              aria-label={`${confidenceLevel} confidence level`}
              className="flex-shrink-0 mt-1 lg:mt-0"
              data-testid="icon-integrity-seal"
            />
            
            <div className="flex-1 min-w-0">
              {/* Primary Statement: Overall Confidence with Tooltip */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex flex-wrap items-center gap-2 mb-1.5 cursor-help">
                    <h3 className={`text-base font-semibold ${colors.text} tabular-nums`} data-testid="text-confidence-status">
                      Verification Status: {Math.round(animatedConfidence)}% Data Confidence
                    </h3>
                    
                    {/* Trend Indicator */}
                    <div 
                      className="flex items-center gap-1"
                      data-testid="trend-indicator"
                    >
                      <TrendIndicator 
                        size={16}
                        direction={trendDirection}
                        aria-label={`Trend: ${trendLabels[trend]}`}
                      />
                      <span className={`text-xs font-medium ${trendColors[trend]} hidden sm:inline`}>
                        {trendLabels[trend]}
                      </span>
                    </div>
                  </div>
                </TooltipTrigger>
                <TooltipContent 
                  className="max-w-md p-4 bg-gray-900 text-white rounded-lg shadow-xl"
                  sideOffset={8}
                  side="bottom"
                >
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <DataIntegritySeal size={20} confidence="high" aria-label="Data confidence" className="flex-shrink-0" />
                      <p className="font-semibold text-blue-100">Data Confidence Score</p>
                    </div>
                    <p className="text-gray-200 leading-relaxed">
                      This score represents the <strong className="text-white">overall reliability of your revenue data</strong> based on platform reconciliation completeness, match accuracy, and data freshness.
                    </p>
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-gray-300">Score Interpretation:</p>
                      <div className="space-y-1.5 text-xs">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-green-500" />
                          <span className="text-gray-300">
                            <strong className="text-green-400">85-100%:</strong> High confidence — Safe for strategic decisions
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-amber-500" />
                          <span className="text-gray-300">
                            <strong className="text-amber-400">70-84%:</strong> Medium confidence — Use with caution
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-red-500" />
                          <span className="text-gray-300">
                            <strong className="text-red-400">&lt;70%:</strong> Low confidence — Wait for verification
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="pt-3 border-t border-gray-700">
                      <p className="text-xs text-gray-400 leading-relaxed">
                        {trend === 'increasing' && (
                          <>
                            <strong className="text-green-400">Increasing:</strong> More transactions are being verified over time
                          </>
                        )}
                        {trend === 'decreasing' && (
                          <>
                            <strong className="text-red-400">Decreasing:</strong> New unverified transactions are outpacing verification
                          </>
                        )}
                        {trend === 'stable' && (
                          <>
                            <strong className="text-gray-300">Stable:</strong> Verification rate is maintaining consistent levels
                          </>
                        )}
                      </p>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
              
              {/* Secondary Metrics Row */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                {/* Transaction Verification Rate with Tooltip */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-muted-foreground cursor-help tabular-nums" data-testid="text-verification-rate">
                        {Math.round(animatedTransactionPercentage)}% of transactions fully verified
                      </span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent 
                    className="max-w-xs p-3 bg-gray-900 text-white rounded-lg shadow-xl"
                    sideOffset={5}
                    side="bottom"
                  >
                    <p className="text-gray-200 leading-relaxed">
                      This represents the <strong className="text-white">percentage of individual transactions</strong> that have been matched with platform records, not the revenue dollar amount.
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      Example: If you have 100 transactions totaling $10,000, and 45 transactions worth $9,000 are verified, this would show 45% (not 90%).
                    </p>
                  </TooltipContent>
                </Tooltip>
                
                {/* Accuracy Level Badge */}
                <div className="flex items-center gap-1.5">
                  <Badge variant="secondary" className={`rounded-full ${colors.badge}`} data-testid="badge-accuracy">
                    {accuracyLabels[confidenceLevel]}
                  </Badge>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT SECTION: Last Update Timestamp */}
          <div className="flex items-center text-xs text-muted-foreground lg:ml-auto flex-shrink-0" data-testid="text-last-updated">
            <Clock className="w-3.5 h-3.5 mr-1.5" aria-hidden="true" />
            <span>
              <span className="hidden sm:inline">Updated </span>
              <span className="font-medium">{lastUpdated}</span>
            </span>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

export default DataConfidenceBar;
