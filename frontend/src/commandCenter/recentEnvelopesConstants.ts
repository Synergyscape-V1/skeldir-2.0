/** Backend-aligned active signal window for Recent TrustEnvelopes — not a frontend row cap. */
export type RecentSignalWindow = '24h' | '7d';

export const MAX_RECENT_ENVELOPES = 25;

/** Visible snapshot rows in the Command Center table — matches channel trust snapshot row count. */
export const RECENT_ENVELOPES_SNAPSHOT_ROW_COUNT = 5;

export const DEFAULT_RECENT_SIGNAL_WINDOW: RecentSignalWindow = '24h';

export function recentSignalWindowMs(window: RecentSignalWindow): number {
  return window === '7d' ? 7 * 24 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
}

export function recentSignalWindowLabel(window: RecentSignalWindow): string {
  return window === '7d' ? 'last 7 days' : 'last 24 hours';
}
