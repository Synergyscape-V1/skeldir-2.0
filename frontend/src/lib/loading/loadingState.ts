import type { CardState } from '../../components/layout/Card/Card';
import type { TableState } from '../../components/layout/Table/Table';
import { LOADING_COPY } from '../copy';
import type { ActiveLoadingPhase } from './useTimedLoading';
import { useTimedLoading } from './useTimedLoading';

export function loadingPhaseToTableState(phase: ActiveLoadingPhase): TableState {
  switch (phase) {
    case 'under_2s':
      return 'loading_under_2s';
    case 'over_2s':
      return 'loading_over_2s';
    case 'over_8s':
      return 'loading_over_8s';
  }
}

export function loadingPhaseToCardState(phase: ActiveLoadingPhase): CardState {
  switch (phase) {
    case 'under_2s':
      return 'loading_under_2s';
    case 'over_2s':
      return 'loading_over_2s';
    case 'over_8s':
      return 'loading_over_8s';
  }
}

export interface TimedTableLoadingProps {
  state: TableState;
  progressCopy?: string;
  onRetry?: () => void;
}

export function resolveTimedTableLoading(
  phase: ActiveLoadingPhase | null,
  options?: { progressCopy?: string; onRetry?: () => void },
): TimedTableLoadingProps | null {
  if (!phase) return null;
  const state = loadingPhaseToTableState(phase);
  const progressCopy =
    phase === 'over_2s' || phase === 'over_8s'
      ? (options?.progressCopy ?? LOADING_COPY.progress)
      : undefined;
  const onRetry = phase === 'over_8s' ? options?.onRetry : undefined;
  return { state, progressCopy, onRetry };
}

export function useTimedTableLoading(
  active: boolean,
  options?: { progressCopy?: string; onRetry?: () => void },
): TimedTableLoadingProps | null {
  const phase = useTimedLoading(active);
  return resolveTimedTableLoading(phase, options);
}

export function useTimedCardLoading(
  active: boolean,
  options?: { progressCopy?: string; onRetry?: () => void },
): { state: CardState; progressCopy?: string; onRetry?: () => void } | null {
  const phase = useTimedLoading(active);
  if (!phase) return null;
  return {
    state: loadingPhaseToCardState(phase),
    progressCopy:
      phase === 'over_2s' || phase === 'over_8s'
        ? (options?.progressCopy ?? LOADING_COPY.progress)
        : undefined,
    onRetry: phase === 'over_8s' ? options?.onRetry : undefined,
  };
}
