/**
 * A5-FORGE Priority Action Rows — Tabular Inline Actions
 *
 * Priority actions as highlighted table-like rows, consistent with
 * FORGE's data-forward tabular philosophy. Each row is severity-coded
 * with a left border and inline impact values.
 */
import { AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { type PriorityAction } from '../types';

const severity = {
  critical: { icon: AlertTriangle, border: 'border-l-destructive', bg: 'bg-destructive/5', label: 'text-destructive' },
  warning: { icon: AlertCircle, border: 'border-l-unverified', bg: 'bg-unverified/5', label: 'text-unverified' },
  info: { icon: Info, border: 'border-l-primary', bg: 'bg-primary/5', label: 'text-primary' },
} as const;

interface Props {
  actions: PriorityAction[];
  loading?: boolean;
}

export function ForgePriorityRows({ actions, loading }: Props) {
  if (loading) {
    return (
      <div className="border border-border rounded-md overflow-hidden">
        {[0, 1, 2].map(i => (
          <div key={i} className="flex items-center gap-3 px-4 py-2.5 border-b border-border/50 last:border-b-0">
            <Skeleton className="h-4 w-4 rounded" />
            <Skeleton className="h-4 w-48 flex-1" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
    );
  }

  if (actions.length === 0) return null;

  return (
    <div className="border border-border rounded-md overflow-hidden">
      {actions.map(action => {
        const s = severity[action.severity];
        const Icon = s.icon;
        return (
          <div
            key={action.id}
            className={cn(
              'flex items-center gap-3 px-4 py-2.5 border-l-3 border-b border-border/30 last:border-b-0 transition-colors',
              s.border, s.bg
            )}
          >
            <Icon className={cn('h-4 w-4 shrink-0', s.label)} aria-hidden="true" />
            <div className="flex-1 min-w-0">
              <span className="text-sm text-foreground font-medium">{action.title}</span>
              {action.affectedChannel && (
                <span className="ml-2 text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                  {action.affectedChannel}
                </span>
              )}
            </div>
            <span className="font-mono text-xs text-muted-foreground tabular-nums shrink-0">
              {action.estimatedImpact}
            </span>
          </div>
        );
      })}
    </div>
  );
}
