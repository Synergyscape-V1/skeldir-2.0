/**
 * RevenueOverview Component - FE-UX-032, FE-UX-033
 * 
 * Displays verified and unverified revenue metrics with typography dominance and elevation system:
 * - Primary financial figures: 48px (achieving 3:1 ratio with secondary text)
 * - Secondary percentages: 16px
 * - Both cards: 2dp elevation (floating treatment for visual alignment)
 * - Verified card: Green left border (status indicator)
 * - Unverified card: Amber left border (status indicator)
 * - Hover states: Elevation increases to 3dp on both cards (2→3dp)
 * 
 * Adheres to Material Design 3 elevation principles and industry benchmarks
 */

import { CheckCircle, AlertCircle, TrendingUp } from 'lucide-react';
import { useAnimatedValue } from '@/hooks/use-animated-value';

interface RevenueOverviewProps {
  verifiedRevenue: number;
  unverifiedRevenue: number;
  verifiedPercentage: number;
  unverifiedPercentage: number;
  verifiedTrend?: number;
  unverifiedTrend?: number;
}

export const RevenueOverview: React.FC<RevenueOverviewProps> = ({
  verifiedRevenue,
  unverifiedRevenue,
  verifiedPercentage,
  unverifiedPercentage,
  verifiedTrend,
  unverifiedTrend,
}) => {
  const animatedVerifiedRevenue = useAnimatedValue(verifiedRevenue, 1000);
  const animatedUnverifiedRevenue = useAnimatedValue(unverifiedRevenue, 1000);

  const formatCurrency = (amount: number): string => {
    return amount.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const formatPercentage = (percentage: number, decimals: number = 1): string => {
    return percentage.toFixed(decimals);
  };

  return (
    <div className="revenue-overview-container">
      <div className="revenue-cards-grid grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ===== VERIFIED REVENUE CARD ===== */}
        <div 
          className="verified-revenue-card 
                     bg-card
                     border border-card-border
                     rounded-md
                     p-6
                     border-l-4
                     flex flex-col
                     elevation-unverified
                     elevation-transition
                     hover:elevation-unverified-hover"
          style={{
            borderLeftColor: 'hsl(var(--verified))',
          }}
          role="article"
          aria-label="Verified revenue card"
          data-testid="card-verified-revenue"
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              Verified Revenue
            </h3>
            <CheckCircle 
              className="w-5 h-5"
              style={{ color: 'hsl(var(--verified))' }}
              aria-label="Verified status"
            />
          </div>

          <div className="flex items-baseline space-x-2 mb-2">
            <p 
              className="text-5xl font-bold text-foreground tabular-nums leading-tight"
              style={{
                fontSize: '48px',
                lineHeight: '1.1',
                letterSpacing: '-0.02em'
              }}
              data-testid="text-verified-amount"
            >
              ${formatCurrency(animatedVerifiedRevenue)}
            </p>
            
            {verifiedTrend !== undefined && verifiedTrend > 0 && (
              <span 
                className="inline-flex items-center text-sm font-medium"
                style={{ color: 'hsl(var(--verified))' }}
                data-testid="trend-verified"
              >
                <TrendingUp className="w-4 h-4 mr-1" />
                +{formatPercentage(verifiedTrend)}%
              </span>
            )}
          </div>

          <p className="text-base font-semibold text-muted-foreground mt-3" data-testid="text-verified-percentage">
            {formatPercentage(verifiedPercentage, 1)}% of total revenue
          </p>

          <p className="text-xs text-muted-foreground mt-4 pt-4 border-t border-border">
            Revenue confirmed through direct platform integrations
          </p>
        </div>

        {/* ===== UNVERIFIED REVENUE CARD ===== */}
        <div 
          className="unverified-revenue-card 
                     bg-card
                     border border-card-border
                     rounded-md
                     p-6
                     border-l-4
                     flex flex-col
                     elevation-unverified
                     elevation-transition
                     hover:elevation-unverified-hover"
          style={{
            borderLeftColor: 'hsl(var(--unverified))',
          }}
          role="article"
          aria-label="Unverified revenue card"
          data-testid="card-unverified-revenue"
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              Unverified Revenue
            </h3>
            <AlertCircle 
              className="w-5 h-5"
              style={{ color: 'hsl(var(--unverified))' }}
              aria-label="Pending verification"
            />
          </div>

          <div className="flex items-baseline space-x-2 mb-2">
            <p 
              className="text-5xl font-bold text-foreground tabular-nums leading-tight"
              style={{
                fontSize: '48px',
                lineHeight: '1.1',
                letterSpacing: '-0.02em'
              }}
              data-testid="text-unverified-amount"
            >
              ${formatCurrency(animatedUnverifiedRevenue)}
            </p>
            
            {unverifiedTrend !== undefined && unverifiedTrend < 0 && (
              <span 
                className="inline-flex items-center text-sm font-medium"
                style={{ color: 'hsl(var(--verified))' }}
                data-testid="trend-unverified"
              >
                <TrendingUp className="w-4 h-4 mr-1 rotate-180" />
                {formatPercentage(Math.abs(unverifiedTrend))}%
              </span>
            )}
          </div>

          <p className="text-base font-semibold text-muted-foreground mt-3" data-testid="text-unverified-percentage">
            {formatPercentage(unverifiedPercentage, 1)}% of total revenue
          </p>

          <p className="text-xs text-muted-foreground mt-4 pt-4 border-t border-border">
            Estimated revenue requiring additional validation
          </p>
        </div>
      </div>
    </div>
  );
};

export default RevenueOverview;
