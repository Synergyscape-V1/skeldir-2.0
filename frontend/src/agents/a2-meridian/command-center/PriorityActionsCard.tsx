/**
 * A2-MERIDIAN PriorityActionsCard — Severity-Coded Actions Card
 */

import { AlertCircle, AlertTriangle, Info, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { type PriorityAction } from '../types';

interface PriorityActionsCardProps {
  actions: PriorityAction[];
  loading?: boolean;
}

const sev = {
  critical: { icon: AlertCircle, cls: 'text-destructive', border: 'border-l-destructive', bg: 'bg-destructive/5' },
  warning: { icon: AlertTriangle, cls: 'text-unverified', border: 'border-l-unverified', bg: 'bg-unverified/5' },
  info: { icon: Info, cls: 'text-primary', border: 'border-l-primary', bg: 'bg-primary/5' },
} as const;

export function PriorityActionsCard({ actions, loading }: PriorityActionsCardProps) {
  if (loading) {
    return (
      <Card className="p-6" aria-busy="true">
        <CardHeader className="p-0 pb-4"><Skeleton className="h-4 w-32" /></CardHeader>
        <CardContent className="p-0 space-y-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <CardHeader className="p-0 pb-4">
        <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Priority Actions
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0 space-y-2">
        {actions.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">
            All channels operating within expected parameters. Next model update in 30 minutes.
          </p>
        ) : (
          actions.map((action) => {
            const cfg = sev[action.severity];
            const Icon = cfg.icon;
            return (
              <a
                key={action.id}
                href={action.actionUrl}
                className={cn(
                  'group flex items-start gap-3 p-4 rounded-md border-l-2 transition-colors duration-200',
                  cfg.border, cfg.bg,
                  'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
                )}
              >
                <Icon className={cn('h-4 w-4 mt-0.5 flex-shrink-0', cfg.cls)} aria-hidden="true" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">{action.title}</p>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{action.description}</p>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <span className="font-mono text-xs font-medium text-foreground">{action.estimatedImpact}</span>
                  <ChevronRight className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity duration-120" />
                </div>
              </a>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
