import { PlatformVarianceCard } from './PlatformVarianceCard';
import type { PlatformVariance } from '@shared/schema';

interface PlatformVarianceGridNewProps {
  platformVariances: PlatformVariance[];
  highlightedPlatform?: string | null;
  onPlatformClick?: (platformId: string) => void;
}

export function PlatformVarianceGridNew({
  platformVariances,
  highlightedPlatform,
  onPlatformClick,
}: PlatformVarianceGridNewProps) {
  // Sort platforms by risk amount (highest first) for visual priority
  const sortedPlatforms = [...platformVariances]
    .filter(p => p.unmatchedRevenue > 0) // Only show platforms with variance
    .sort((a, b) => b.unmatchedRevenue - a.unmatchedRevenue);

  if (sortedPlatforms.length === 0) {
    return null;
  }

  return (
    <div className="platform-variance-grid" data-testid="platform-variance-grid-new">
      <h3 className="text-lg font-semibold text-foreground mb-4">
        Platform Variance Breakdown
      </h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-end">
        {sortedPlatforms.map((platform) => {
          // Calculate variance percentage (what % of total transactions are unmatched)
          const variancePercentage = platform.totalTransactions > 0 
            ? ((platform.unmatchedCount / platform.totalTransactions) * 100).toFixed(1)
            : '0.0';

          // Generate platform logo URL based on platform name
          const platformLogo = `/assets/platform-logos/${platform.name.toLowerCase().replace(/\s+/g, '-')}-logo.svg`;

          return (
            <PlatformVarianceCard
              key={platform.id}
              platformName={platform.name}
              platformLogo={platformLogo}
              unmatchedCount={platform.unmatchedCount}
              riskAmount={platform.unmatchedRevenue}
              variancePercentage={parseFloat(variancePercentage)}
              matchRate={platform.matchPercentage}
              isHighlighted={highlightedPlatform === platform.id}
              onClick={() => onPlatformClick?.(platform.id)}
            />
          );
        })}
      </div>
    </div>
  );
}
