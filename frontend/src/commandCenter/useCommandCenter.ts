import { useCallback, useEffect, useRef, useState } from 'react';
import { getDefaultCommandCenterClient } from './commandCenterClient';
import type { CommandCenterAggregate, CommandCenterOutcome } from './types';
import { getAuthState } from '../auth/sessionStore';
import type { ActiveLoadingPhase } from '../lib/loading';
import { useTimedLoading } from '../lib/loading';

export interface UseCommandCenterResult {
  outcome: CommandCenterOutcome | null;
  aggregate: CommandCenterAggregate | null;
  loading: boolean;
  loadingPhase: ActiveLoadingPhase | null;
  retry: () => void;
}

export function useCommandCenter(): UseCommandCenterResult {
  const [outcome, setOutcome] = useState<CommandCenterOutcome | null>(null);
  const [loading, setLoading] = useState(true);
  const loadStarted = useRef<number>(0);
  const abortRef = useRef<AbortController | null>(null);
  const loadingPhase = useTimedLoading(loading);

  const fetchData = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    loadStarted.current = Date.now();

    const { tenant } = getAuthState();
    if (!tenant) {
      setOutcome({ kind: 'empty_tenant', message: 'Workspace required.' });
      setLoading(false);
      return;
    }

    try {
      const result = await getDefaultCommandCenterClient().fetchAggregate(
        tenant.tenantId,
        controller.signal,
      );
      if (!controller.signal.aborted) {
        setOutcome(result);
      }
    } catch {
      if (!controller.signal.aborted) {
        setOutcome({
          kind: 'trust_api_read_failed',
          message: 'Trust API read failed. No financial truth was changed.',
        });
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void fetchData();
    return () => abortRef.current?.abort();
  }, [fetchData]);

  const aggregate =
    outcome?.kind === 'loaded' ||
    outcome?.kind === 'stale' ||
    outcome?.kind === 'partial'
      ? outcome.aggregate
      : null;

  return { outcome, aggregate, loading, loadingPhase, retry: fetchData };
}

