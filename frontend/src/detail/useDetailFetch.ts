import { useCallback, useEffect, useRef, useState } from 'react';
import type { ActiveLoadingPhase } from '../lib/loading';
import { useTimedLoading } from '../lib/loading';
import type { DetailOutcomeKind } from './types';

export interface UseDetailFetchResult<TLoaded> {
  kind: DetailOutcomeKind | 'idle';
  data: TLoaded | null;
  message?: string;
  loadingPhase: ActiveLoadingPhase | null;
  reload: () => void;
}

export function useDetailFetch<TLoaded>(
  fetcher: (signal: AbortSignal) => Promise<
    | { kind: 'loaded'; detail: TLoaded }
    | { kind: Exclude<DetailOutcomeKind, 'loaded' | 'loading' | 'long_loading'>; message: string }
  >,
  deps: unknown[],
): UseDetailFetchResult<TLoaded> {
  const [kind, setKind] = useState<DetailOutcomeKind | 'idle'>('idle');
  const [data, setData] = useState<TLoaded | null>(null);
  const [message, setMessage] = useState<string>();
  const activeRef = useRef(0);
  const isLoading = kind === 'loading' || kind === 'idle';
  const loadingPhase = useTimedLoading(isLoading);

  const load = useCallback(() => {
    const requestId = ++activeRef.current;
    const controller = new AbortController();
    setKind('loading');
    setData(null);
    setMessage(undefined);

    void fetcher(controller.signal)
      .then((outcome) => {
        if (activeRef.current !== requestId) return;
        if (outcome.kind === 'loaded') {
          setKind('loaded');
          setData(outcome.detail);
        } else {
          setKind(outcome.kind);
          setMessage(outcome.message);
        }
      })
      .catch((err: unknown) => {
        if (activeRef.current !== requestId) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setKind('network_error');
        setMessage('Network unavailable. Detail was not updated.');
      });

    return () => {
      controller.abort();
    };
  }, deps);

  useEffect(() => load(), [load]);

  return { kind, data, message, loadingPhase, reload: load };
}

