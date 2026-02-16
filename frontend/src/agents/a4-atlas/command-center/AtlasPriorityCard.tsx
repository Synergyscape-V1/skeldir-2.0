/**
 * A4-ATLAS Priority Action Card — Standalone Severity-Coded Card
 *
 * Each priority action rendered as its own card with left severity border.
 * Card-first philosophy: every piece of information is a scannable unit.
 */
import { AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { type PriorityAction } from '../types';

const severity = {
  critical: { icon: AlertTriangle, border: 'border-l-destructive', bg: 'bg-destructive/5', text: 'text-destructive' },
  warning: { icon: AlertCircle, border: 'border-l-unverified', bg: 'bg-unverified/5', text: 'text-unverified' },
  info: { icon: Info, border: 'border-l-primary', bg: 'bg-primary/5', text: 'text-primary' },
} as const;

interface Props {
  actions: PriorityAction[];
  loading?: boolean;
}

export function AtlasPriorityCard({ actions, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map(i => (
          <Card key={i} className="p-4">
            <CardContent className="p-0 space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-24" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (actions.length === 0) return null;

  return (
    <div className="space-y-3">
      {actions.map(action => {
        const s = severity[action.severity];
        const Icon = s.icon;
        return (
          <Card key={action.id} className={cn('p-4 border-l-4', s.border, s.bg)}>
            <CardContent className="p-0">
              <div className="flex items-start gap-3">
                <Icon className={cn('h-4 w-4 mt-0.5 shrink-0', s.text)} aria-hidden="true" />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-medium text-foreground truncate">{action.title}</h3>
                    <span className="font-mono text-xs text-muted-foreground shrink-0 tabular-nums">{action.estimatedImpact}</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{action.description}</p>
                  {action.affectedChannel && (
                    <span className="inline-block text-[10px] font-medium text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                      {action.affectedChannel}
                    </span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
