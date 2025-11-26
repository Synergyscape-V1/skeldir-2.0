import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface PulsingDotProps {
  tooltip?: string;
}

export default function PulsingDot({ tooltip = "Actively checking for updates..." }: PulsingDotProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className="absolute z-20"
            style={{
              top: '12px',
              right: '12px',
            }}
            data-testid="pulsing-dot"
          >
            <div
              className="rounded-full"
              style={{
                width: '10px',
                height: '10px',
                backgroundColor: '#3B82F6',
                animation: 'pulse-dot 1.5s ease-in-out infinite',
              }}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{tooltip}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
