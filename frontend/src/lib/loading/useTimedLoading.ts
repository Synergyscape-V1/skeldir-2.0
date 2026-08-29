import { useEffect, useState } from 'react';
import type { LoadingPhase } from '../types';
import { LOADING_OVER_8S_MS, LOADING_UNDER_2S_MS } from './constants';

export type ActiveLoadingPhase = Exclude<LoadingPhase, 'idle'>;

/**
 * Drives the spec-mandated loading ladder: skeleton-only under 2s, progress copy after 2s, retry after 8s.
 * Returns null when `active` is false.
 */
export function useTimedLoading(active: boolean): ActiveLoadingPhase | null {
  const [phase, setPhase] = useState<ActiveLoadingPhase | null>(active ? 'under_2s' : null);

  useEffect(() => {
    if (!active) {
      setPhase(null);
      return;
    }

    setPhase('under_2s');
    const over2Timer = window.setTimeout(() => setPhase('over_2s'), LOADING_UNDER_2S_MS);
    const over8Timer = window.setTimeout(() => setPhase('over_8s'), LOADING_OVER_8S_MS);

    return () => {
      clearTimeout(over2Timer);
      clearTimeout(over8Timer);
    };
  }, [active]);

  if (!active) return null;
  return phase ?? 'under_2s';
}
