import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewClaims } from '../ledger/permissions';
import { LEDGER_COPY } from '../ledger/copy';
import { COMMAND_CENTER_COPY } from './copy';
import {
  B210_CLAIMED_DISCREPANCY_BPS_BASE,
  B210_SNAPSHOT_CADENCE_HOURS,
  buildB210RevenueSnapshotSeries,
} from './revenueSnapshotFixtures';
import { MAX_TREND_POINTS } from './trendConstants';
import type { TrendPoint, VerifiedRevenueTrendMeta } from './types';

export type RevenueSnapshotOutcome =
  | {
      kind: 'loaded';
      points: TrendPoint[];
      meta: VerifiedRevenueTrendMeta;
    }
  | { kind: 'permission_denied'; message: string }
  | { kind: 'unavailable'; reason: string; variant: 'sparse_data' | 'no_commerce_truth' }
  | { kind: 'trust_api_read_failed'; message: string };

export interface RevenueSnapshotClient {
  listSnapshots(
    tenantId: string,
    options?: { windowDays?: number },
    signal?: AbortSignal,
  ): Promise<RevenueSnapshotOutcome>;
}

let testMode: 'default' | 'unavailable' | 'trust_api_failed' = 'default';
let testDelayMs = 0;
let pointsOverride: TrendPoint[] | null = null;

export function setRevenueSnapshotTestMode(mode: typeof testMode): void {
  testMode = mode;
}

export function resetRevenueSnapshotTestMode(): void {
  testMode = 'default';
  testDelayMs = 0;
  pointsOverride = null;
}

export function setRevenueSnapshotDelayForTests(ms: number): void {
  testDelayMs = ms;
}

export function setRevenueSnapshotPointsOverrideForTests(points: TrendPoint[] | null): void {
  pointsOverride = points;
}

function resolveTrendMeta(points: TrendPoint[]): VerifiedRevenueTrendMeta {
  const hasClaimedOverlay = points.some(
    (point) => point.status !== 'unavailable' && point.claimedRevenueMinor != null,
  );
  return {
    snapshotCadenceHours: B210_SNAPSHOT_CADENCE_HOURS,
    sourceField: 'verified_revenue_minor',
    benchmarkDiscrepancyBps: B210_CLAIMED_DISCREPANCY_BPS_BASE,
    claimedOverlayEnabled: hasClaimedOverlay,
  };
}

function buildLoadedOutcome(points: TrendPoint[]): RevenueSnapshotOutcome {
  const plottable = points.filter((point) => point.status !== 'unavailable');
  if (plottable.length === 0) {
    return {
      kind: 'unavailable',
      reason: COMMAND_CENTER_COPY.trendEmptyBody,
      variant: 'no_commerce_truth',
    };
  }
  if (plottable.every((point) => point.verifiedRevenueMinor === 0n)) {
    return {
      kind: 'unavailable',
      reason: COMMAND_CENTER_COPY.trendNoEventsBody,
      variant: 'sparse_data',
    };
  }
  return {
    kind: 'loaded',
    points: points.slice(-MAX_TREND_POINTS),
    meta: resolveTrendMeta(points),
  };
}

export function createRevenueSnapshotClient(): RevenueSnapshotClient {
  return {
    async listSnapshots(tenantId, _options, signal) {
      if (testDelayMs > 0) {
        await new Promise<void>((resolve, reject) => {
          const timer = setTimeout(resolve, testDelayMs);
          signal?.addEventListener('abort', () => {
            clearTimeout(timer);
            reject(new DOMException('Aborted', 'AbortError'));
          });
        });
      }

      if (signal?.aborted) {
        throw new DOMException('Aborted', 'AbortError');
      }

      const role = getCurrentUserRole();
      if (!canViewClaims(role)) {
        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };
      }

      if (!tenantId) {
        return {
          kind: 'unavailable',
          reason: COMMAND_CENTER_COPY.trendEmptyBody,
          variant: 'no_commerce_truth',
        };
      }

      if (testMode === 'trust_api_failed') {
        return { kind: 'trust_api_read_failed', message: COMMAND_CENTER_COPY.trustApiReadFailed };
      }

      if (testMode === 'unavailable') {
        return {
          kind: 'unavailable',
          reason: COMMAND_CENTER_COPY.trendEmptyBody,
          variant: 'no_commerce_truth',
        };
      }

      const points = pointsOverride ?? buildB210RevenueSnapshotSeries();
      return buildLoadedOutcome(points);
    },
  };
}

let defaultClient: RevenueSnapshotClient | null = null;

export function getDefaultRevenueSnapshotClient(): RevenueSnapshotClient {
  if (!defaultClient) defaultClient = createRevenueSnapshotClient();
  return defaultClient;
}

export function resetDefaultRevenueSnapshotClient(): void {
  defaultClient = null;
  resetRevenueSnapshotTestMode();
}
