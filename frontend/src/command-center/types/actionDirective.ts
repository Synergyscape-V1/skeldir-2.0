/**
 * Action Directives — Command Center (Skeldir §3.4)
 */

export type DirectiveStatus = 'pending' | 'approved' | 'rejected' | 'executing' | 'completed';

export interface DirectiveConfidenceRange {
  lower: number;
  upper: number;
  estimate: number;
  bucket: 'narrow' | 'medium' | 'wide';
  lowerLabel: string;
  upperLabel: string;
  actionImplication?: string;
}

export interface ActionDirective {
  id: string;
  priority: 1 | 2 | 3 | 4 | 5;
  headline: string;
  projectedOutcomeText: string;
  confidenceRange: DirectiveConfidenceRange | null;
  drivers: string[];
  primaryAction: {
    label: string;
    route?: string;
    asyncJobRequired?: boolean;
  };
  secondaryAction?: {
    label: string;
    type: 'dismiss' | 'snooze';
  };
  status: DirectiveStatus;
  /** ISO date for ordering */
  createdAt: string;
  /** Preformatted relative label */
  relativeTime: string;
}

export const MAX_ACTION_DIRECTIVES = 5;

export function sortDirectives(list: ActionDirective[]): ActionDirective[] {
  return [...list].sort((a, b) => {
    if (a.priority !== b.priority) return a.priority - b.priority;
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });
}
