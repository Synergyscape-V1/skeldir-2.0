import { TrendingDown, ChevronRight } from 'lucide-react';
import type { PlatformVariance } from '@shared/schema';
import { Card } from '@/components/ui/card';
import { PlatformLogo } from '@/components/common/PlatformLogo';

interface PlatformVarianceGridProps {
  platformVariances: PlatformVariance[];
  onPlatformClick: (platformId: string) => void;
  highlightedPlatform?: string | null;
}

export function PlatformVarianceGrid({
  platformVariances,
  onPlatformClick,
  highlightedPlatform,
}: PlatformVarianceGridProps) {
  if (platformVariances.length === 0) {
    return null;
  }

  return (
    <div className="mt-6 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-foreground/70 uppercase tracking-wide">
          Variance by Platform
        </h3>
        <span className="text-xs text-muted-foreground">
          Click platform to view details
        </span>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {platformVariances.map((platform) => {
          const isHighlighted = highlightedPlatform === platform.id;
          const hasVariance = platform.unmatchedCount > 0;
          
          return (
            <button
              key={platform.id}
              onClick={() => hasVariance && onPlatformClick(platform.id)}
              className={`
                relative bg-card border-2 rounded-md p-4 
                transition-all duration-200 text-left
                ${hasVariance ? 'hover-elevate active-elevate-2 cursor-pointer' : 'opacity-50 cursor-default'}
                ${isHighlighted ? 'border-primary shadow-lg ring-2 ring-primary/30' : 'border-border'}
                focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2
              `}
              disabled={!hasVariance}
              aria-label={`View ${platform.unmatchedCount} unmatched transactions for ${platform.name}`}
              data-testid={`button-platform-${platform.id}`}
            >
              {hasVariance && (
                <div className="absolute top-2 right-2">
                  <div className="flex items-center space-x-1 px-1.5 py-0.5 bg-destructive/10 rounded-full border border-destructive/20">
                    <TrendingDown className="w-3 h-3 text-destructive" />
                    <span className="text-xs font-medium text-destructive">
                      {(100 - platform.matchPercentage).toFixed(0)}%
                    </span>
                  </div>
                </div>
              )}
              
              <div className="mb-3">
                <PlatformLogo 
                  platform={platform.name}
                  size="md"
                  showFallback={true}
                  className="drop-shadow-sm"
                />
              </div>
              
              <div className="mb-2">
                <div className="flex items-baseline space-x-1">
                  <span 
                    className={`text-2xl font-bold ${hasVariance ? 'text-foreground' : 'text-green-600 dark:text-green-500'}`}
                    data-testid={`text-unmatched-count-${platform.id}`}
                  >
                    {platform.unmatchedCount}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    unmatched
                  </span>
                </div>
              </div>
              
              <div className="flex flex-wrap items-center justify-between gap-1 mb-2">
                <span className="text-xs text-foreground/70" data-testid={`text-match-percentage-${platform.id}`}>
                  {platform.matchPercentage}% match
                </span>
                {hasVariance && (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </div>
              
              <div className="text-xs text-muted-foreground">
                {platform.unmatchedCount} of {platform.totalTransactions} transactions
              </div>
              
              {platform.unmatchedRevenue > 0 && (
                <div className="mt-2 pt-2 border-t border-border">
                  <span className="text-xs text-foreground/80" data-testid={`text-unmatched-revenue-${platform.id}`}>
                    ${platform.unmatchedRevenue.toLocaleString('en-US', { 
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2 
                    })}
                  </span>
                  <span className="text-xs text-muted-foreground ml-1">
                    at risk
                  </span>
                </div>
              )}
            </button>
          );
        })}
      </div>
      
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-xs text-foreground/70">
        <span data-testid="text-total-unmatched">
          Total unmatched: {platformVariances.reduce((sum, p) => sum + p.unmatchedCount, 0)} transactions
        </span>
        <span data-testid="text-affected-platforms">
          Affected platforms: {platformVariances.filter(p => p.unmatchedCount > 0).length}
        </span>
      </div>
    </div>
  );
}
