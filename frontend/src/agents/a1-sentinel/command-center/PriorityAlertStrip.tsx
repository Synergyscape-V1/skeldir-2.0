/**
 * A1-SENTINEL PriorityAlertStrip — Inline Alert Rows
 *
 * Compact severity-coded rows between metrics and channel table.
 * Each row: severity left border → title → impact → action link.
 *
 * Master Skill citations:
 *   - Copy axiom: lead with outcome, quantify impact
 *   - Error states: what happened + why + what to do
 *   - Persona A: PriorityActionsSection P90 ≤ 1.5s
 *   - Zero mental math: estimated impact always quantified
 */

import { AlertTriangle, AlertCircle, Info, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { type PriorityAction } from '../types';

interface PriorityAlertStripProps {
  actions: PriorityAction[];
  loading?: boolean;
}

const severityConfig = {
  critical: {
    border: 'border-l-destructive',
    icon: AlertCircle,
    iconClass: 'text-destructive',
    bgClass: 'bg-destructive/5',
    label: 'Critical',
  },
  warning: {
    border: 'border-l-unverified',
    icon: AlertTriangle,
    iconClass: 'text-unverified',
    bgClass: 'bg-unverified/5',
    label: 'Warning',
  },
  info: {
    border: 'border-l-primary',
    icon: Info,
    iconClass: 'text-primary',
    bgClass: 'bg-primary/5',
    label: 'Info',
  },
} as const;

export function PriorityAlertStrip({ actions, loading = false }: PriorityAlertStripProps) {
  if (loading) {
    return (
      <div className="space-y-1" aria-busy="true">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-3 px-3 py-2 border-l-2 border-l-muted rounded-sm bg-muted/30">
            <Skeleton className="h-4 w-4 rounded-full" />
            <Skeleton className="h-3 w-48" />
            <Skeleton className="h-3 w-16 ml-auto" />
          </div>
        ))}
      </div>
    );
  }

  if (actions.length === 0) {
    return (
      <div className="px-3 py-2 text-xs text-muted-foreground border border-border rounded-sm">
        All channels operating within expected parameters. Next model update in 30 minutes.
      </div>
    );
  }

  return (
    <div className="space-y-1" role="list" aria-label="Priority actions requiring attention">
      {actions.map((action) => {
        const config = severityConfig[action.severity];
        const Icon = config.icon;

        return (
          <a
            key={action.id}
            href={action.actionUrl}
            className={cn(
              'group flex items-center gap-3 px-3 py-2 border-l-2 rounded-sm transition-colors duration-120',
              config.border,
              config.bgClass,
              'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1'
            )}
            role="listitem"
            aria-label={`${config.label}: ${action.title}. Impact: ${action.estimatedImpact}`}
          >
            <Icon className={cn('h-3.5 w-3.5 flex-shrink-0', config.iconClass)} aria-hidden="true" />

            <span className="text-xs font-medium text-foreground truncate">
              {action.title}
            </span>

            {action.affectedChannel && (
              <span className="text-[10px] text-muted-foreground whitespace-nowrap hidden sm:inline">
                {action.affectedChannel}
              </span>
            )}

            <span className="ml-auto flex items-center gap-1 whitespace-nowrap">
              <span className="font-mono text-xs font-medium text-foreground">
                {action.estimatedImpact}
              </span>
              <ChevronRight className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity duration-120" aria-hidden="true" />
            </span>
          </a>
        );
      })}
    </div>
  );
}
