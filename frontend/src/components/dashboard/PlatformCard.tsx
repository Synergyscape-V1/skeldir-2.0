import { PlatformLogo } from '@/components/common/PlatformLogo';
import { ReconciliationStatusIcon } from '@/components/icons';
import { TooltipAdvanced, TooltipAdvancedTrigger, TooltipAdvancedContent } from '@/components/ui/tooltip-advanced';
import { useDashboardHighlight } from '@/contexts/DashboardHighlightContext';

interface PlatformCardProps {
  platform: string;
  platformDisplayName: string;
  status: 'verified' | 'partial' | 'pending' | 'error' | 'unverified';
  matchPercentage?: number;
  revenue: number;
  percentageOfTotal: number;
  isVerified: boolean;
}

// Status-specific tooltip content generator
const getStatusTooltipContent = (status: string, matchPercentage: number, platformName: string) => {
  const tooltips = {
    verified: {
      icon: <ReconciliationStatusIcon size={20} status="complete" aria-label="Verified" />,
      title: 'Fully Verified',
      titleColor: 'text-green-100',
      description: `${platformName} transactions have been successfully matched with platform records at ${matchPercentage}% confidence. This revenue is safe to use for budget decisions.`,
      details: 'All transactions from this platform have corresponding entries in your payment processor records with matching amounts, timestamps, and customer identifiers.',
      action: undefined,
    },
    partial: {
      icon: <ReconciliationStatusIcon size={20} status="pending" aria-label="Partial match" />,
      title: 'Partial Match',
      titleColor: 'text-amber-100',
      description: `${platformName} transactions matched at ${matchPercentage}% confidence. Some discrepancies detected that require investigation.`,
      details: 'Partial matches occur when transaction amounts differ slightly, timestamps don\'t align perfectly, or customer identifiers are missing. Review the reconciliation report for details.',
      action: 'Click "Investigate" to view specific mismatches',
    },
    unverified: {
      icon: <ReconciliationStatusIcon size={20} status="pending" aria-label="Unverified" />,
      title: 'Unverified Revenue',
      titleColor: 'text-amber-100',
      description: `${platformName} transactions have not yet been verified through platform reconciliation. This revenue is estimated and requires validation.`,
      details: 'Unverified revenue represents transactions that are pending reconciliation with platform records. As the system syncs with payment processors, this revenue will automatically move to verified status.',
      action: 'Typically takes 15-60 minutes for verification to complete',
    },
    pending: {
      icon: <ReconciliationStatusIcon size={20} status="processing" aria-label="Processing" />,
      title: 'Pending Reconciliation',
      titleColor: 'text-blue-100',
      description: `${platformName} is currently syncing transaction data. Verification will complete once platform API responds.`,
      details: 'Pending status typically resolves within 15-60 minutes depending on platform API rate limits and data volume. The system checks for updates every 30 seconds.',
      action: 'Refresh the page if pending for more than 2 hours',
    },
    error: {
      icon: <ReconciliationStatusIcon size={20} status="failed" aria-label="Failed" />,
      title: 'Sync Failed',
      titleColor: 'text-red-100',
      description: `${platformName} encountered an error during synchronization. Manual intervention required.`,
      details: 'Common causes: API authentication expired, platform temporarily unavailable, or rate limit exceeded. Check integration settings.',
      action: 'Click "Retry Sync" or reconnect the platform',
    },
  };

  return tooltips[status as keyof typeof tooltips] || tooltips.pending;
};

export default function PlatformCard({
  platform,
  platformDisplayName,
  status,
  matchPercentage = 0,
  revenue,
  percentageOfTotal,
  isVerified,
}: PlatformCardProps) {
  
  const { setHighlight, clearHighlight, isVerifiedHighlighted, isUnverifiedHighlighted } = useDashboardHighlight();
  
  // Determine if this card should be highlighted
  const shouldHighlight = isVerified ? isVerifiedHighlighted() : isUnverifiedHighlighted();
  
  // Status color mapping for badge
  const getStatusBadgeColor = (status: string): string => {
    const colorMap: Record<string, string> = {
      'verified': '#10B981',      // Green
      'partial': '#F59E0B',       // Amber
      'pending': '#3B82F6',       // Blue
      'error': '#EF4444',         // Red
      'unverified': '#F59E0B',    // Amber
    };
    return colorMap[status] || '#6B7280'; // Gray fallback
  };

  // Status icon mapping - rendered in center of card
  const getStatusIcon = (status: string) => {
    switch(status) {
      case 'verified':
        return <ReconciliationStatusIcon size={32} status="complete" aria-label="Verified status" />;
      case 'partial':
      case 'unverified':
        return <ReconciliationStatusIcon size={32} status="pending" aria-label="Pending status" />;
      case 'pending':
        return <ReconciliationStatusIcon size={32} status="processing" aria-label="Processing status" />;
      case 'error':
        return <ReconciliationStatusIcon size={32} status="failed" aria-label="Error status" />;
      default:
        return <ReconciliationStatusIcon size={32} status="pending" aria-label="Unknown status" />;
    }
  };

  // Map status to label text
  const getStatusLabel = (status: string): string => {
    switch (status) {
      case 'verified':
        return 'Verified';
      case 'partial':
      case 'unverified':
        return 'Partial Match';
      case 'pending':
        return 'Pending';
      case 'error':
        return 'Error';
      default:
        return status;
    }
  };

  // Determine top border color based on verification status (FE-UX-016)
  // Uses CSS custom properties from FE-UX-015: --verified (green) and --unverified (amber)
  const topBorderStyle = isVerified 
    ? { borderTopColor: 'hsl(var(--verified) / 1)', borderTopWidth: '3px' }
    : { borderTopColor: 'hsl(var(--unverified) / 1)', borderTopWidth: '3px' };

  const tooltipContent = getStatusTooltipContent(status, matchPercentage, platformDisplayName);

  return (
    <TooltipAdvanced
      placement="top"
      sideOffset={12}
      collisionPadding={16}
      protectedElements={['[data-protected-zone="verification-status"]', '[data-protected-zone="verification-flow"]']}
    >
      <TooltipAdvancedTrigger asChild>
        <div 
          className={`
            platform-card
            relative flex flex-col min-h-[120px] p-4 border border-card-border rounded-md bg-card 
            hover:shadow-sm transition-shadow duration-200 ease-out cursor-help
            ${shouldHighlight ? (isVerified 
              ? 'ring-2 ring-green-600 ring-opacity-40' 
              : 'ring-2 ring-amber-600 ring-opacity-40'
            ) : ''}
          `}
          style={topBorderStyle}
          data-testid={`card-platform-${platform.toLowerCase()}`}
          role="button"
          tabIndex={0}
          aria-label={`${platformDisplayName} ${getStatusLabel(status)} platform. Revenue: $${revenue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}. Hover or focus to highlight ${isVerified ? 'verified' : 'unverified'} revenue in overview.`}
          onMouseEnter={() => setHighlight(isVerified ? 'verified' : 'unverified')}
          onMouseLeave={() => clearHighlight()}
          onFocus={() => setHighlight(isVerified ? 'verified' : 'unverified')}
          onBlur={() => clearHighlight()}
        >
      {/* Platform Logo - Top Left (STANDARDIZED) */}
      <div className="absolute top-3 left-3 z-10" data-testid={`logo-${platform.toLowerCase()}`}>
        <PlatformLogo 
          platform={platform}
          size="lg"
          showFallback={true}
          className="drop-shadow-sm"
        />
      </div>

      {/* Status Badge - Top Right (REPOSITIONED FROM LEFT) */}
      <div 
        className="absolute top-3 right-3 z-10"
        style={{
          width: '20px',
          height: '20px',
          borderRadius: '50%',
          backgroundColor: getStatusBadgeColor(status)
        }}
        aria-label={`Status indicator: ${getStatusLabel(status)}`}
        data-testid={`badge-status-${platform.toLowerCase()}`}
      />

      {/* Pulsing Active Indicator - Top Right (if pending) */}
      {status === 'pending' && (
        <div 
          className="absolute top-3 right-10 z-10 animate-pulse"
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            backgroundColor: '#3B82F6',
          }}
          title="Actively checking for updates..."
          data-testid={`pulse-${platform.toLowerCase()}`}
        />
      )}

      {/* Card Content */}
      <div className="flex flex-col h-full justify-between mt-6">
        {/* Status Label and Match Percentage */}
        <div className="flex items-start justify-between mb-2">
          <h4 className="text-sm font-bold text-card-foreground" data-testid={`text-platform-${platform.toLowerCase()}`}>
            {platformDisplayName} {getStatusLabel(status)}
          </h4>
          {matchPercentage !== undefined && (
            <span className="text-xs font-semibold text-muted-foreground" data-testid={`text-match-${platform.toLowerCase()}`}>
              ({matchPercentage}% match)
            </span>
          )}
        </div>

        {/* Status Icon - Center */}
        <div className="flex justify-center my-2">
          {getStatusIcon(status)}
        </div>

        {/* Revenue Amount */}
        <div className="text-center">
          <p className="text-base font-semibold mb-1 text-card-foreground" data-testid={`text-amount-${platform.toLowerCase()}`}>
            ${revenue.toLocaleString('en-US', { 
              minimumFractionDigits: 2, 
              maximumFractionDigits: 2 
            })}
          </p>
          <p className="text-xs text-muted-foreground" data-testid={`text-percentage-${platform.toLowerCase()}`}>
            {percentageOfTotal.toFixed(2)}% of {isVerified ? 'verified' : 'unverified'} revenue
          </p>
        </div>
      </div>
        </div>
      </TooltipAdvancedTrigger>
      <TooltipAdvancedContent 
        className="max-w-xs p-4 !bg-gray-900 dark:!bg-gray-900 text-white rounded-lg shadow-xl border-gray-700"
        showArrow={true}
      >
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            {tooltipContent.icon}
            <p className={`font-semibold ${tooltipContent.titleColor}`}>{tooltipContent.title}</p>
          </div>
          <p className="text-gray-200 leading-relaxed">
            {tooltipContent.description}
          </p>
          <div className="pt-3 border-t border-gray-700">
            <p className="text-xs text-gray-400 leading-relaxed">
              {tooltipContent.details}
            </p>
          </div>
          {tooltipContent.action && (
            <div className="pt-2">
              <p className="text-xs text-blue-300 leading-relaxed">
                {tooltipContent.action}
              </p>
            </div>
          )}
        </div>
      </TooltipAdvancedContent>
    </TooltipAdvanced>
  );
}
