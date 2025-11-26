import { useMemo } from 'react';
import { Info, X } from 'lucide-react';
import { formatCurrency } from '@/utils/currencyFormat';
import { useCalloutDismissal } from '@/hooks/useCalloutDismissal';

const STORAGE_KEY = 'skeldir_math_validation_dismissed';

export interface PlatformRevenue {
  id: string;
  name: string;
  amount: number;
  status: 'verified' | 'partial' | 'pending' | 'failed';
}

export interface MathematicalValidationCalloutProps {
  verifiedTotal: number;
  unverifiedTotal: number;
  verifiedPlatforms: PlatformRevenue[];
  unverifiedPlatforms: PlatformRevenue[];
  className?: string;
  onDismiss?: () => void;
}

/**
 * Mathematical Validation Callout Component
 * 
 * Displays explicit breakdown showing how individual platform revenue amounts
 * sum to verified and unverified totals shown in the Data Integrity Monitor.
 * Helps users understand the mathematical relationship between platform-level
 * data and aggregate totals.
 * 
 * Note: Currently uses platformData (separate from Revenue Overview API data).
 * In production, these data sources should be unified for consistency.
 */
export const MathematicalValidationCallout: React.FC<MathematicalValidationCalloutProps> = ({
  verifiedTotal,
  unverifiedTotal,
  verifiedPlatforms,
  unverifiedPlatforms,
  className = '',
  onDismiss,
}) => {
  const { isVisible, dismiss } = useCalloutDismissal(STORAGE_KEY);

  const breakdowns = useMemo(() => {
    const createBreakdown = (platforms: PlatformRevenue[]): string => {
      if (platforms.length === 0) return 'No platforms';
      
      if (platforms.length === 1) {
        return `${platforms[0].name} (${formatCurrency(platforms[0].amount)})`;
      }
      
      return platforms
        .map((p) => `${p.name} (${formatCurrency(p.amount)})`)
        .join(' + ');
    };

    return {
      verified: createBreakdown(verifiedPlatforms),
      unverified: createBreakdown(unverifiedPlatforms),
    };
  }, [verifiedPlatforms, unverifiedPlatforms]);

  const calculatedSums = useMemo(() => {
    const verifiedSum = verifiedPlatforms.reduce((sum, p) => sum + p.amount, 0);
    const unverifiedSum = unverifiedPlatforms.reduce((sum, p) => sum + p.amount, 0);

    if (import.meta.env.DEV) {
      const verifiedDiff = Math.abs(verifiedSum - verifiedTotal);
      const unverifiedDiff = Math.abs(unverifiedSum - unverifiedTotal);
      
      if (verifiedDiff > 0.01) {
        console.warn(
          `[MathematicalValidationCallout] Verified total mismatch:`,
          `Expected: ${verifiedTotal}, Calculated: ${verifiedSum}, Diff: ${verifiedDiff}`
        );
      }
      
      if (unverifiedDiff > 0.01) {
        console.warn(
          `[MathematicalValidationCallout] Unverified total mismatch:`,
          `Expected: ${unverifiedTotal}, Calculated: ${unverifiedSum}, Diff: ${unverifiedDiff}`
        );
      }
    }

    return { verified: verifiedSum, unverified: unverifiedSum };
  }, [verifiedPlatforms, unverifiedPlatforms, verifiedTotal, unverifiedTotal]);

  const handleDismiss = () => {
    dismiss();
    onDismiss?.();
  };

  if (!isVisible) return null;

  return (
    <div 
      className={`
        mathematical-validation-callout
        bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6
        flex items-start justify-between shadow-sm
        transition-all duration-300 ease-in-out
        hover:shadow-md
        ${className}
      `}
      role="complementary"
      aria-label="Revenue breakdown explanation"
      data-testid="callout-math-validation"
    >
      <div className="flex items-start space-x-3 flex-1 min-w-0">
        <Info 
          className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" 
          aria-hidden="true"
        />
        
        <div className="text-sm text-gray-700 dark:text-gray-300 space-y-3 flex-1 min-w-0">
          <p className="font-semibold text-gray-900 dark:text-gray-100 text-base">
            Platform Revenue Breakdown
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
            The Data Integrity Monitor below shows how these platform amounts contribute to your totals
          </p>
          
          <div className="space-y-1.5">
            <div className="flex items-center space-x-2 flex-wrap">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 shadow-sm">
                ✓ Verified
              </span>
              <span className="font-bold text-green-700 dark:text-green-400 text-base tabular-nums">
                {formatCurrency(verifiedTotal)}
              </span>
              {verifiedPlatforms.length > 0 && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  ({verifiedPlatforms.length} platform{verifiedPlatforms.length !== 1 ? 's' : ''})
                </span>
              )}
            </div>
            
            {verifiedPlatforms.length > 0 ? (
              <div className="ml-0 sm:ml-20 pl-4 border-l-2 border-green-200 dark:border-green-700">
                <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed break-words">
                  {breakdowns.verified}
                </p>
              </div>
            ) : (
              <p className="ml-0 sm:ml-20 text-xs italic text-gray-500 dark:text-gray-400">
                No verified platforms yet
              </p>
            )}
          </div>
          
          <div className="space-y-1.5">
            <div className="flex items-center space-x-2 flex-wrap">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 shadow-sm">
                ⚠ Unverified
              </span>
              <span className="font-bold text-amber-700 dark:text-amber-400 text-base tabular-nums">
                {formatCurrency(unverifiedTotal)}
              </span>
              {unverifiedPlatforms.length > 0 && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  ({unverifiedPlatforms.length} platform{unverifiedPlatforms.length !== 1 ? 's' : ''})
                </span>
              )}
            </div>
            
            {unverifiedPlatforms.length > 0 ? (
              <div className="ml-0 sm:ml-20 pl-4 border-l-2 border-amber-200 dark:border-amber-700">
                <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed break-words">
                  {breakdowns.unverified}
                </p>
              </div>
            ) : (
              <p className="ml-0 sm:ml-20 text-xs italic text-gray-500 dark:text-gray-400">
                No unverified platforms
              </p>
            )}
          </div>

          <div className="pt-2 border-t border-blue-100 dark:border-blue-800">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              <span className="font-medium text-gray-700 dark:text-gray-300">Total Revenue:</span>{' '}
              {formatCurrency(verifiedTotal + unverifiedTotal)}
            </p>
          </div>
        </div>
      </div>

      <button
        onClick={handleDismiss}
        className="
          text-gray-400 hover:text-gray-600 dark:hover:text-gray-300
          transition-colors duration-200
          ml-4 flex-shrink-0
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded
          p-1
        "
        aria-label="Dismiss breakdown explanation"
        title="Dismiss this explanation"
        data-testid="button-dismiss-callout"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};

MathematicalValidationCallout.displayName = 'MathematicalValidationCallout';
