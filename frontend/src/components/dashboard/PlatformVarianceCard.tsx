import { AlertTriangle, TrendingUp } from 'lucide-react';

interface PlatformVarianceCardProps {
  platformName: string;
  platformLogo: string;
  unmatchedCount: number;
  riskAmount: number;
  variancePercentage: number;
  matchRate: number;
  isHighlighted?: boolean;
  onClick?: () => void;
}

/**
 * Calculate proportional card height based on risk amount
 * Formula from forensic analysis: baseHeight + (riskAmount / 1000)
 * Examples: $42,500 → 162px | $8,250 → 128px | $3,120 → 123px
 */
const calculateCardHeight = (riskAmount: number): number => {
  const baseHeight = 120;
  const scaleFactor = 1000;
  const calculatedHeight = baseHeight + (riskAmount / scaleFactor);
  
  // Enforce min/max bounds
  return Math.max(120, Math.min(calculatedHeight, 200));
};

/**
 * Classify risk level for visual treatment
 */
const getRiskLevel = (riskAmount: number): 'high' | 'medium' | 'low' => {
  if (riskAmount > 30000) return 'high';
  if (riskAmount > 10000) return 'medium';
  return 'low';
};

const riskStyles = {
  high: {
    border: 'border-red-500 dark:border-red-600 border-[3px]',
    shadow: 'shadow-alert hover:shadow-lg',
    icon: true,
    badge: 'bg-red-100 dark:bg-red-950/30 text-red-800 dark:text-red-400',
  },
  medium: {
    border: 'border-amber-400 dark:border-amber-500 border-2',
    shadow: 'shadow-md hover:shadow-lg',
    icon: false,
    badge: 'bg-amber-100 dark:bg-amber-950/30 text-amber-800 dark:text-amber-400',
  },
  low: {
    border: 'border-border border',
    shadow: 'shadow-sm hover:shadow-md',
    icon: false,
    badge: 'bg-muted text-muted-foreground',
  },
};

export function PlatformVarianceCard({
  platformName,
  platformLogo,
  unmatchedCount,
  riskAmount,
  variancePercentage,
  matchRate,
  isHighlighted = false,
  onClick,
}: PlatformVarianceCardProps) {
  const cardHeight = calculateCardHeight(riskAmount);
  const riskLevel = getRiskLevel(riskAmount);
  const styles = riskStyles[riskLevel];

  return (
    <div
      className={`variance-card bg-card rounded-md p-6 flex flex-col justify-between 
                  transition-all duration-200 cursor-pointer
                  ${styles.border} ${styles.shadow}
                  ${isHighlighted ? 'ring-4 ring-primary/30 border-primary' : ''}`}
      style={{ height: `${cardHeight}px` }}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.();
        }
      }}
      aria-label={`${platformName} variance details: ${unmatchedCount} unmatched transactions, $${riskAmount.toLocaleString()} at risk`}
      data-testid={`card-platform-variance-${platformName.toLowerCase().replace(/\s+/g, '-')}`}
    >
      {/* Platform header */}
      <div>
        <div className="flex items-center justify-between mb-3">
          {/* Platform logo */}
          <img
            src={platformLogo}
            alt={`${platformName} logo`}
            className="h-6 object-contain"
            data-testid={`img-platform-logo-${platformName.toLowerCase().replace(/\s+/g, '-')}`}
          />
          
          {/* High risk alert icon */}
          {styles.icon && (
            <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-500" aria-label="High risk" data-testid="icon-high-risk" />
          )}
        </div>

        {/* Platform name */}
        <h3 className="text-base font-semibold text-foreground mb-3" data-testid="text-platform-name">
          {platformName}
        </h3>

        {/* PRIMARY METRIC: Risk amount at 32px */}
        <p className="text-3xl font-bold text-red-700 dark:text-red-500 mb-2 tabular-nums leading-none" data-testid="text-risk-amount">
          ${riskAmount.toLocaleString('en-US', { 
            minimumFractionDigits: 2, 
            maximumFractionDigits: 2 
          })}
        </p>

        {/* SECONDARY METRIC: Unmatched count */}
        <p className="text-sm font-medium text-foreground/80 mb-1" data-testid="text-unmatched-count">
          {unmatchedCount.toLocaleString()} unmatched transactions
        </p>

        {/* Match rate indicator */}
        <div className="flex items-center text-xs text-muted-foreground mt-2" data-testid="text-match-rate">
          <TrendingUp className="w-3.5 h-3.5 mr-1 text-green-600 dark:text-green-500" />
          <span>{matchRate}% overall match rate</span>
        </div>
      </div>

      {/* Footer: Variance percentage badge */}
      <div className="mt-4 pt-4 border-t border-border">
        <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${styles.badge}`} data-testid="badge-variance-percentage">
          {variancePercentage}% of platform revenue
        </span>
      </div>
    </div>
  );
}
