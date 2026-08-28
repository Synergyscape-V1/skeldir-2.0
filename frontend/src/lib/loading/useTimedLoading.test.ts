import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LOADING_OVER_8S_MS, LOADING_UNDER_2S_MS } from './constants';
import { loadingPhaseToTableState, useTimedTableLoading } from './loadingState';
import { useTimedLoading } from './useTimedLoading';

describe('useTimedLoading', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('stays skeleton-only under 2s', () => {
    const { result } = renderHook(() => useTimedLoading(true));
    expect(result.current).toBe('under_2s');
    act(() => {
      vi.advanceTimersByTime(LOADING_UNDER_2S_MS - 1);
    });
    expect(result.current).toBe('under_2s');
  });

  it('escalates to over_2s and over_8s', () => {
    const { result } = renderHook(() => useTimedLoading(true));
    act(() => {
      vi.advanceTimersByTime(LOADING_UNDER_2S_MS);
    });
    expect(result.current).toBe('over_2s');
    act(() => {
      vi.advanceTimersByTime(LOADING_OVER_8S_MS - LOADING_UNDER_2S_MS);
    });
    expect(result.current).toBe('over_8s');
  });

  it('returns null when inactive', () => {
    const { result } = renderHook(() => useTimedLoading(false));
    expect(result.current).toBeNull();
  });
});

describe('useTimedTableLoading', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('maps phases to table states and retry', () => {
    const onRetry = vi.fn();
    const { result } = renderHook(() => useTimedTableLoading(true, { onRetry }));
    expect(result.current?.state).toBe('loading_under_2s');
    expect(result.current?.progressCopy).toBeUndefined();
    act(() => {
      vi.advanceTimersByTime(LOADING_UNDER_2S_MS);
    });
    expect(result.current?.state).toBe('loading_over_2s');
    expect(result.current?.progressCopy).toContain('Still loading verified trust state');
    act(() => {
      vi.advanceTimersByTime(LOADING_OVER_8S_MS - LOADING_UNDER_2S_MS);
    });
    expect(result.current?.state).toBe('loading_over_8s');
    expect(result.current?.onRetry).toBe(onRetry);
  });
});

describe('loadingPhaseToTableState', () => {
  it('covers all phases', () => {
    expect(loadingPhaseToTableState('under_2s')).toBe('loading_under_2s');
    expect(loadingPhaseToTableState('over_2s')).toBe('loading_over_2s');
    expect(loadingPhaseToTableState('over_8s')).toBe('loading_over_8s');
  });
});
