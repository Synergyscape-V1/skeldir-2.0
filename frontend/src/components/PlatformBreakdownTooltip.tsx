import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import StatusIcon from '@/components/StatusIcon';
import type { PlatformRevenue } from '@shared/schema';

interface PlatformBreakdownTooltipProps {
  platforms: PlatformRevenue[];
  children: React.ReactNode;
}

export default function PlatformBreakdownTooltip({ platforms, children }: PlatformBreakdownTooltipProps) {
  const getStatusType = (status: string): 'high' | 'medium' | 'pending' | 'multiple' => {
    switch (status) {
      case 'verified':
        return 'high';
      case 'partial':
        return 'medium';
      case 'pending':
        return 'pending';
      default:
        return 'pending';
    }
  };

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          {children}
        </TooltipTrigger>
        <TooltipContent
          className="p-3 rounded-lg"
          data-testid="tooltip-platform-breakdown"
        >
          <div className="space-y-2">
            <p className="text-sm font-semibold mb-2">
              Platform Breakdown:
            </p>
            {platforms.map((platform) => (
              <div key={platform.platform} className="flex items-center gap-2">
                <StatusIcon
                  type={getStatusType(platform.status)}
                  size={16}
                  ariaLabel={`${platform.platform} status: ${platform.status}`}
                />
                <span className="text-sm">
                  {platform.platform}:
                </span>
                <span className="text-sm font-semibold ml-auto">
                  ${platform.amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className="text-xs text-gray-300">
                  ({platform.status})
                </span>
              </div>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
