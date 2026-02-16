/**
 * A3-PRISM Polling Hook
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { usePollingManager } from '@/hooks/use-polling-manager';
import { type CommandCenterState, FIXTURES } from '../types';

export function usePrismPolling() {
  const [state, setState] = useState<CommandCenterState>({ status: 'loading' });
  const [isUpdating, setIsUpdating] = useState(false);
  const ref = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    const t = setTimeout(() => setState(FIXTURES.ready), 1200);
    return () => clearTimeout(t);
  }, []);

  const handleDashboard = useCallback(async () => {
    setIsUpdating(true);
    if (ref.current) clearTimeout(ref.current);
    ref.current = setTimeout(() => setIsUpdating(false), 600);
    setState(prev => prev.status !== 'ready' ? prev : { ...prev, data: { ...prev.data, lastUpdated: new Date().toISOString() } });
  }, []);

  const handleChannel = useCallback(async () => {}, []);
  const dp = usePollingManager({ intervalMs: 30_000, onPoll: handleDashboard });
  const cp = usePollingManager({ intervalMs: 300_000, onPoll: handleChannel });
  void cp;

  const retry = useCallback(() => { setState({ status: 'loading' }); setTimeout(() => setState(FIXTURES.ready), 800); }, []);

  return { state, isPolling: dp.isActive, isUpdating, lastUpdated: dp.lastPollTime, retry };
}
