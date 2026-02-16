/**
 * A3-PRISM PriorityActions — Compact action rows
 */
import { AlertCircle, AlertTriangle, Info, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { type PriorityAction } from '../types';

const sev = {
  critical: { icon: AlertCircle, cls: 'text-destructive', border: 'border-l-destructive', bg: 'bg-destructive/5' },
  warning: { icon: AlertTriangle, cls: 'text-unverified', border: 'border-l-unverified', bg: 'bg-unverified/5' },
  info: { icon: Info, cls: 'text-primary', border: 'border-l-primary', bg: 'bg-primary/5' },
} as const;

export function PrismPriorityActions({ actions, loading }: { actions: PriorityAction[]; loading?: boolean }) {
  if (loading) return <div className="space-y-1">{[1,2,3].map(i => <Skeleton key={i} className="h-10 w-full" />)}</div>;

  if (!actions.length) return <p className="text-xs text-muted-foreground py-2">All channels within expected parameters.</p>;

  return (
    <div className="space-y-1" role="list" aria-label="Priority actions">
      {actions.map(a => {
        const c = sev[a.severity]; const Icon = c.icon;
        return (
          <a key={a.id} href={a.actionUrl} role="listitem"
            className={cn('group flex items-center gap-2 px-3 py-2 border-l-2 rounded-sm transition-colors duration-120', c.border, c.bg, 'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring')}>
            <Icon className={cn('h-3.5 w-3.5 flex-shrink-0', c.cls)} />
            <span className="text-xs font-medium text-foreground truncate flex-1">{a.title}</span>
            <span className="font-mono text-[10px] text-muted-foreground">{a.estimatedImpact}</span>
            <ChevronRight className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity duration-120" />
          </a>
        );
      })}
    </div>
  );
}
