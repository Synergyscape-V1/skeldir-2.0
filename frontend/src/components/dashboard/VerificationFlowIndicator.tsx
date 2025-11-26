import { useEffect, useState } from 'react';
import { Search, RefreshCw, CheckCircle } from 'lucide-react';

interface VerificationFlowIndicatorProps {
  verifiedPercentage: number; // 0-100: Percentage of total revenue that is verified
  processingPercentage?: number; // 0-100: Percentage currently in reconciliation
  transactionCount?: {
    total: number;
    verified: number;
    processing: number;
    unverified: number;
  };
  showTransactionBreakdown?: boolean; // Toggle transaction count display
  animationDuration?: number; // milliseconds for progress bar animation
  className?: string;
}

export const VerificationFlowIndicator: React.FC<VerificationFlowIndicatorProps> = ({
  verifiedPercentage,
  processingPercentage = 0,
  transactionCount,
  showTransactionBreakdown = false,
  animationDuration = 1000,
  className = '',
}) => {
  const [animatedPercentage, setAnimatedPercentage] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  // Calculate unverified percentage
  const unverifiedPercentage = 100 - verifiedPercentage - processingPercentage;

  // Smooth percentage animation on mount and update
  useEffect(() => {
    setIsAnimating(true);
    const startValue = animatedPercentage;
    const endValue = verifiedPercentage;
    const startTime = Date.now();

    const animate = () => {
      const currentTime = Date.now();
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / animationDuration, 1);

      // Easing function (ease-out cubic)
      const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
      const easedProgress = easeOutCubic(progress);

      const currentValue = startValue + (endValue - startValue) * easedProgress;
      setAnimatedPercentage(currentValue);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setIsAnimating(false);
      }
    };

    requestAnimationFrame(animate);
  }, [verifiedPercentage, animationDuration]);

  // Determine status badge color
  const getStatusColor = () => {
    if (verifiedPercentage >= 90) return 'text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/50';
    if (verifiedPercentage >= 70) return 'text-blue-700 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/50';
    return 'text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/50';
  };

  // Determine status text
  const getStatusText = () => {
    if (verifiedPercentage >= 90) return 'Excellent verification coverage';
    if (verifiedPercentage >= 70) return 'Good verification progress';
    if (verifiedPercentage >= 50) return 'Verification in progress';
    return 'Initial verification stage';
  };

  return (
    <div 
      className={`verification-flow-indicator bg-card border border-card-border rounded-lg px-3 py-2 mb-6 shadow-sm
                  transition-all duration-300 ease-in-out
                  ${className}`}
      role="region"
      aria-label="Revenue verification progress"
      data-testid="verification-flow-indicator"
      data-protected-zone="verification-flow"
    >
      {/* Compact Header - Single Row */}
      <div className="flex items-center justify-between mb-1.5">
        <h3 className="text-xs font-semibold text-card-foreground" data-testid="text-flow-title">
          Revenue Verification Flow
          {showTransactionBreakdown && transactionCount && (
            <span className="ml-2 text-muted-foreground font-normal tabular-nums" data-testid="count-total">
              ({transactionCount.total.toLocaleString()})
            </span>
          )}
        </h3>
        <div className="flex items-center gap-2">
          <span 
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor()}`}
            data-testid="badge-verification-percentage"
            aria-live="polite"
          >
            {Math.round(animatedPercentage)}%
          </span>
          <span className="text-xs text-muted-foreground hidden sm:inline" data-testid="text-status-message">
            {getStatusText()}
          </span>
        </div>
      </div>

      {/* Progress Bar Container with accessible progressbar role */}
      <div className="relative mb-1.5">
        {/* Background track with progressbar semantics */}
        <div 
          className="h-2.5 bg-muted rounded-full overflow-hidden relative"
          role="progressbar"
          aria-valuenow={Math.round(animatedPercentage)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Verification progress: ${Math.round(animatedPercentage)}% verified`}
        >
          {/* Unverified segment (base layer) */}
          <div 
            className="absolute left-0 top-0 h-full bg-gradient-to-r from-amber-200 to-amber-300 dark:from-amber-800 dark:to-amber-700"
            style={{ width: '100%' }}
            data-testid="progress-unverified-base"
          />
          
          {/* Processing segment (middle layer) */}
          {processingPercentage > 0 && (
            <div 
              className="absolute top-0 h-full bg-gradient-to-r from-blue-300 to-blue-400 dark:from-blue-700 dark:to-blue-600 transition-all duration-1000 ease-out"
              style={{ 
                left: `${unverifiedPercentage}%`,
                width: `${processingPercentage}%`
              }}
              data-testid="progress-processing"
            />
          )}
          
          {/* Verified segment (top layer) */}
          <div 
            className={`absolute right-0 top-0 h-full bg-gradient-to-r from-green-400 to-green-500 dark:from-green-700 dark:to-green-600
                        transition-all ease-out ${isAnimating ? 'duration-1000' : 'duration-300'}`}
            style={{ width: `${animatedPercentage}%` }}
            data-testid="progress-verified"
          >
            {/* Animated shine effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-30 animate-shine" />
          </div>
        </div>
      </div>

      {/* Compact Stage Labels - Horizontal Layout */}
      <div className="flex items-center justify-between gap-2 text-xs">
        {/* Unverified Stage - Compact */}
        <div className="flex items-center gap-1 flex-1" data-testid="stage-unverified">
          <div className="flex items-center justify-center w-4 h-4 bg-amber-100 dark:bg-amber-900/30 rounded-full flex-shrink-0">
            <Search className="w-2.5 h-2.5 text-amber-600 dark:text-amber-500" />
          </div>
          <div className="flex items-center gap-1">
            <span className="font-medium text-card-foreground whitespace-nowrap hidden sm:inline">Unverified</span>
            <span className="text-muted-foreground tabular-nums" data-testid="percentage-unverified">
              {Math.round(unverifiedPercentage)}%
            </span>
            {showTransactionBreakdown && transactionCount && (
              <span className="text-muted-foreground/70 tabular-nums hidden xl:inline" data-testid="count-unverified">
                ({transactionCount.unverified.toLocaleString()})
              </span>
            )}
          </div>
        </div>

        {/* Processing Stage - Compact */}
        <div className="flex items-center gap-1 flex-1 justify-center" data-testid="stage-processing">
          <div className="flex items-center justify-center w-4 h-4 bg-blue-100 dark:bg-blue-900/30 rounded-full flex-shrink-0">
            <RefreshCw className={`w-2.5 h-2.5 text-blue-600 dark:text-blue-500 ${processingPercentage > 0 ? 'animate-spin-slow' : ''}`} />
          </div>
          <div className="flex items-center gap-1">
            <span className="font-medium text-card-foreground whitespace-nowrap hidden sm:inline">Processing</span>
            <span className="text-muted-foreground tabular-nums" data-testid="percentage-processing">
              {Math.round(processingPercentage)}%
            </span>
            {showTransactionBreakdown && transactionCount && (
              <span className="text-muted-foreground/70 tabular-nums hidden xl:inline" data-testid="count-processing">
                ({transactionCount.processing.toLocaleString()})
              </span>
            )}
          </div>
        </div>

        {/* Verified Stage - Compact */}
        <div className="flex items-center gap-1 flex-1 justify-end" data-testid="stage-verified">
          <div className="flex items-center justify-center w-4 h-4 bg-green-100 dark:bg-green-900/30 rounded-full flex-shrink-0">
            <CheckCircle className="w-2.5 h-2.5 text-green-600 dark:text-green-500" />
          </div>
          <div className="flex items-center gap-1">
            <span className="font-medium text-card-foreground whitespace-nowrap hidden sm:inline">Verified</span>
            <span className="text-green-700 dark:text-green-400 font-semibold tabular-nums" data-testid="percentage-verified">
              {Math.round(animatedPercentage)}%
            </span>
            {showTransactionBreakdown && transactionCount && (
              <span className="text-muted-foreground/70 tabular-nums hidden xl:inline" data-testid="count-verified">
                ({transactionCount.verified.toLocaleString()})
              </span>
            )}
          </div>
        </div>
      </div>

    </div>
  );
};

VerificationFlowIndicator.displayName = 'VerificationFlowIndicator';
