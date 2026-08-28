import { buildClaimTrustDrawerHref } from '../trustIndex/envelopeClaimRouting';
import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewClaims, canViewChannels, canViewTrustIndex } from '../ledger/permissions';
import { LEDGER_COPY } from '../ledger/copy';
import { getDefaultClaimsLedgerClient } from '../claims/claimsClient';
import { getDefaultRevenueSnapshotClient } from './revenueSnapshotClient';
import { getDefaultTrustIndexClient } from '../trustIndex/trustIndexClient';
import { getDefaultChannelsClient } from '../channels/channelsClient';
import { getDefaultOperationalAuditClient } from '../operationalAudit/operationalAuditClient';
import { MAX_DOM_TABLE_ROWS } from '../operationalAudit/pagination';
import type { SystemHealthState } from '../operationalAudit/types';
import { COMMAND_CENTER_COPY } from './copy';
import { COMMAND_CENTER_CHANNEL_ROWS } from './commandCenterChannelFixtures';
import { COMMAND_CENTER_RECENT_ENVELOPES } from './commandCenterEnvelopeFixtures';
import { fetchAuditActivityStrip } from './commandCenterAuditActivity';
import { sortPriorityIssues } from './prioritySeverity';
import {
  getDefaultSupervisoryProjectionClient,
} from './supervisoryProjectionClient';
import {
  buildRecentEnvelopeFeed,
  mapTrustIndexRowToRecentEnvelope,
} from './recentEnvelopeDisplay';
import { DEFAULT_RECENT_SIGNAL_WINDOW, MAX_RECENT_ENVELOPES } from './recentEnvelopesConstants';
import { buildSummaryMetrics, countHumanMeaningfulTrustIssues } from './summaryMetrics';
import type {
  AuditActivityChip,
  ChannelTrustRow,
  CommandCenterAggregate,
  CommandCenterOutcome,
  CommandCenterTestMode,
  PriorityIssue,
  PrimaryAction,
  RecentEnvelopeRow,
  SummaryMetric,
  TrendPoint,
  VerifiedRevenueTrendMeta,
} from './types';

export const MAX_PRIORITY_ROWS = 10;
export const MAX_CHANNEL_ROWS = 5;
export { MAX_RECENT_ENVELOPES, DEFAULT_RECENT_SIGNAL_WINDOW } from './recentEnvelopesConstants';
export const MAX_AUDIT_CHIPS = 4;
export const AUDIT_ACTIVITY_GRID_SIZE = 4;
export { MAX_TREND_POINTS, MIN_TREND_DAYS } from './trendConstants';
export type { CommandCenterTestMode } from './types';

export interface CommandCenterSubstrateOverrides {
  verifiedRevenueBonus?: bigint;
  trendVerifiedBonus?: bigint;
  trendPointsOverride?: TrendPoint[];
  trendMetaOverride?: VerifiedRevenueTrendMeta;
  channelRowsOverride?: ChannelTrustRow[];
  auditActivityOverride?: AuditActivityChip[];
  recentEnvelopesOverride?: RecentEnvelopeRow[];
  latestEnvelopeIdOverride?: string;
  hasTrustEnvelopeOverride?: boolean;
  priorityIssuesUnsorted?: PriorityIssue[];
  forceHealthState?: SystemHealthState;
}

let testMode: CommandCenterTestMode = 'default';
let testDelayMs = 0;
let testHealthState: SystemHealthState | null = null;
let substrateOverrides: CommandCenterSubstrateOverrides | null = null;

export function setCommandCenterSubstrateOverridesForTests(
  overrides: CommandCenterSubstrateOverrides | null,
): void {
  substrateOverrides = overrides;
}

export function setCommandCenterTestMode(mode: CommandCenterTestMode): void {
  testMode = mode;
}

export function resetCommandCenterTestMode(): void {
  testMode = 'default';
  testDelayMs = 0;
  testHealthState = null;
  substrateOverrides = null;
}

export function setCommandCenterDelayForTests(ms: number): void {
  testDelayMs = ms;
}

export function setCommandCenterHealthStateForTests(state: SystemHealthState): void {
  testHealthState = state;
}

export interface CommandCenterClient {
  fetchAggregate(tenantId: string, signal?: AbortSignal): Promise<CommandCenterOutcome>;
}

type TrendSeries = {
  points: TrendPoint[];
  meta?: VerifiedRevenueTrendMeta;
  unavailable?: { reason: string; variant: 'sparse_data' | 'no_commerce_truth' };
};

function applyTrendBonus(trend: TrendSeries, bonus: bigint | undefined): TrendSeries {
  if (!bonus || trend.points.length === 0) return trend;
  return {
    ...trend,
    points: trend.points.map((point) => ({
      ...point,
      verifiedRevenueMinor: point.verifiedRevenueMinor + bonus,
    })),
  };
}

async function resolvePriorityIssues(
  tenantId: string,
  healthState: SystemHealthState,
  testMode: CommandCenterTestMode,
  signal?: AbortSignal,
): Promise<PriorityIssue[]> {
  if (substrateOverrides?.priorityIssuesUnsorted !== undefined) {
    return sortPriorityIssues(substrateOverrides.priorityIssuesUnsorted).slice(0, MAX_PRIORITY_ROWS);
  }

  const projection = await getDefaultSupervisoryProjectionClient().fetchProjection(
    tenantId,
    { healthState, testMode },
    signal,
  );

  if (projection.kind !== 'loaded') {
    return [];
  }

  return projection.issues.slice(0, MAX_PRIORITY_ROWS);
}

export function resolvePrimaryAction(
  aggregate: CommandCenterAggregate,
  unresolvedCount = aggregate.priorityIssues.length,
): PrimaryAction {
  if (unresolvedCount > 0) {
    return {
      kind: 'review_issues',
      label: COMMAND_CENTER_COPY.reviewIssues(unresolvedCount),
    };
  }
  if (aggregate.priorityIssues.length > 0 && unresolvedCount === 0) {
    return {
      kind: 'go_to_budget',
      label: COMMAND_CENTER_COPY.goToBudgetSimulation,
      href: '/app/budget',
    };
  }
  if (aggregate.hasTrustEnvelope && aggregate.latestEnvelopeId) {
    return {
      kind: 'view_latest_envelope',
      label: COMMAND_CENTER_COPY.viewLatestEnvelope,
      href: buildClaimTrustDrawerHref(aggregate.latestEnvelopeId),
    };
  }
  return {
    kind: 'view_latest_envelope',
    label: COMMAND_CENTER_COPY.viewLatestEnvelope,
    href: '/app/trust',
  };
}

export function createCommandCenterClient(): CommandCenterClient {
  return {
    async fetchAggregate(tenantId, signal) {
      if (testDelayMs > 0) {
        await new Promise<void>((resolve, reject) => {
          const timer = setTimeout(resolve, testDelayMs);
          signal?.addEventListener('abort', () => {
            clearTimeout(timer);
            reject(new DOMException('Aborted', 'AbortError'));
          });
        });
      }

      const role = getCurrentUserRole();
      if (!tenantId) {
        return { kind: 'empty_tenant', message: 'Tenant required for Overview aggregate.' };
      }

      if (testMode === 'cross_tenant_leak') {
        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };
      }

      if (testMode === 'trust_api_failed') {
        return { kind: 'trust_api_read_failed', message: COMMAND_CENTER_COPY.trustApiReadFailed };
      }

      if (!canViewClaims(role) && !canViewTrustIndex(role) && !canViewChannels(role)) {
        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };
      }

      const claimsClient = getDefaultClaimsLedgerClient();
      const trustClient = getDefaultTrustIndexClient();
      const channelsClient = getDefaultChannelsClient();
      const auditClient = getDefaultOperationalAuditClient();

      const [claims, snapshots, envelopes, channels, healthOutcome] = await Promise.all([
        canViewClaims(role)
          ? claimsClient.listClaims(
              tenantId,
              { pageSize: MAX_DOM_TABLE_ROWS, sortKey: 'lastUpdated', sortDirection: 'desc' },
              signal,
            )
          : Promise.resolve({ kind: 'permission_denied' as const, message: LEDGER_COPY.permissionDenied }),
        canViewClaims(role)
          ? getDefaultRevenueSnapshotClient().listSnapshots(tenantId, undefined, signal)
          : Promise.resolve({ kind: 'permission_denied' as const, message: LEDGER_COPY.permissionDenied }),
        canViewTrustIndex(role)
          ? trustClient.listEnvelopes(
              tenantId,
              { pageSize: MAX_RECENT_ENVELOPES, sortKey: 'claimTime', sortDirection: 'desc' },
              signal,
            )
          : Promise.resolve({ kind: 'permission_denied' as const, message: LEDGER_COPY.permissionDenied }),
        canViewChannels(role)
          ? channelsClient.listChannels(tenantId, { pageSize: MAX_CHANNEL_ROWS }, signal)
          : Promise.resolve({ kind: 'permission_denied' as const, message: LEDGER_COPY.permissionDenied }),
        auditClient.getSystemHealth(tenantId, signal),
      ]);

      const healthState: SystemHealthState =
        substrateOverrides?.forceHealthState ??
        testHealthState ??
        (healthOutcome.kind === 'health_api_paused' || testMode === 'kill_switch'
          ? 'api_paused'
          : healthOutcome.kind === 'health_confidence_degraded'
            ? 'confidence_degraded'
            : healthOutcome.kind === 'health_integration_attention'
              ? 'integration_attention'
              : healthOutcome.kind === 'health_fetch_failed'
                ? 'fetch_failed'
                : 'operational');

      const killSwitchActive = healthState === 'api_paused' || testMode === 'kill_switch';
      const envelopeRows = envelopes.kind === 'loaded' ? envelopes.rows : [];
      const hasTrustEnvelope =
        substrateOverrides?.hasTrustEnvelopeOverride ??
        (testMode !== 'no_envelope' && envelopeRows.some((e) => e.status === 'active'));
      const envelopeIdOverride = substrateOverrides?.latestEnvelopeIdOverride;
      const latestEnvelope =
        envelopeIdOverride != null
          ? envelopeRows.find((e) => e.envelopeId === envelopeIdOverride) ??
            envelopeRows.find((e) => e.status === 'active') ??
            envelopeRows[0]
          : envelopeRows.find((e) => e.status === 'active') ?? envelopeRows[0];

      const verifiedTotal =
        (claims.kind === 'loaded'
          ? claims.rows.reduce((acc, row) => acc + row.verifiedRevenueMinor, 0n)
          : 0n) + (substrateOverrides?.verifiedRevenueBonus ?? 0n);
      const reconciledCount =
        claims.kind === 'loaded'
          ? claims.rows.filter((r) => r.verificationStatus === 'verified').length
          : 0;
      const claimRows = claims.kind === 'loaded' ? claims.rows : [];

      const trendBase: TrendSeries =
        testMode === 'trend_unavailable'
          ? {
              points: [],
              unavailable: { reason: COMMAND_CENTER_COPY.trendEmptyBody, variant: 'no_commerce_truth' },
            }
          : snapshots.kind === 'loaded'
            ? { points: snapshots.points, meta: snapshots.meta }
            : snapshots.kind === 'unavailable'
              ? { points: [], unavailable: { reason: snapshots.reason, variant: snapshots.variant } }
              : { points: [], unavailable: { reason: COMMAND_CENTER_COPY.trendEmptyBody, variant: 'no_commerce_truth' } };

      const trend = substrateOverrides?.trendPointsOverride
        ? applyTrendBonus(
            {
              points: substrateOverrides.trendPointsOverride,
              meta: substrateOverrides.trendMetaOverride ?? trendBase.meta,
            },
            substrateOverrides.trendVerifiedBonus,
          )
        : applyTrendBonus(trendBase, substrateOverrides?.trendVerifiedBonus);

      const priorityIssues = await resolvePriorityIssues(tenantId, healthState, testMode, signal);

      const summaryMetrics: SummaryMetric[] = buildSummaryMetrics({
        claimsRows: claimRows,
        verifiedRevenueMinor: verifiedTotal,
        trendPoints: trend.points,
        priorityIssues,
        killSwitchActive,
      });

      const channelRows: ChannelTrustRow[] = substrateOverrides?.channelRowsOverride
        ? substrateOverrides.channelRowsOverride.slice(0, MAX_CHANNEL_ROWS)
        : channels.kind === 'loaded'
          ? COMMAND_CENTER_CHANNEL_ROWS.slice(0, MAX_CHANNEL_ROWS)
          : [];

      const recentSignalWindow = DEFAULT_RECENT_SIGNAL_WINDOW;
      const recentSourceRows: RecentEnvelopeRow[] = substrateOverrides?.recentEnvelopesOverride
        ? substrateOverrides.recentEnvelopesOverride
        : envelopeRows.length > 0
          ? envelopeRows.map(mapTrustIndexRowToRecentEnvelope)
          : COMMAND_CENTER_RECENT_ENVELOPES;
      const recentEnvelopes = buildRecentEnvelopeFeed(recentSourceRows, {
        window: recentSignalWindow,
      });

      const auditActivity: AuditActivityChip[] = substrateOverrides?.auditActivityOverride
        ? substrateOverrides.auditActivityOverride.slice(0, MAX_AUDIT_CHIPS)
        : await fetchAuditActivityStrip(tenantId, signal);

      const trustIssuesCount = countHumanMeaningfulTrustIssues(priorityIssues);

      const aggregate: CommandCenterAggregate = {
        tenantId,
        lastUpdatedAt: new Date().toISOString(),
        freshness: testMode === 'stale' ? 'stale' : testMode === 'partial' ? 'partial' : 'fresh',
        staleReason: testMode === 'stale' ? COMMAND_CENTER_COPY.staleAggregate : undefined,
        healthState,
        trustApiReadFailed: false,
        killSwitchActive,
        hasTrustEnvelope,
        latestEnvelopeId:
          substrateOverrides?.latestEnvelopeIdOverride ?? latestEnvelope?.envelopeId ?? null,
        summaryMetrics,
        priorityIssues,
        trendPoints: trend.points,
        trendMeta: trend.meta,
        trendUnavailable: trend.unavailable,
        channelRows,
        recentEnvelopes,
        recentEnvelopesSignalWindow: recentSignalWindow,
        auditActivity,
        openExceptionsCount: trustIssuesCount,
        claimsReconciledCount: reconciledCount,
        sourceTrace: {
          summary: 'claims_ledger+exceptions_queue+policy_settings',
          trend: 'b210_revenue_snapshots',
          channels: 'channels_overview',
          envelopes: 'trust_index',
          audit: 'audit_ledger',
          health: 'operational_audit_health',
          priority: 'supervisory_projection',
        },
      };

      if (testMode === 'stale') {
        return { kind: 'stale', aggregate, message: COMMAND_CENTER_COPY.staleAggregate };
      }
      if (testMode === 'partial') {
        return {
          kind: 'partial',
          aggregate: { ...aggregate, channelRows: [], trendUnavailable: trend.unavailable },
          message: COMMAND_CENTER_COPY.partialAggregate,
        };
      }

      return { kind: 'loaded', aggregate };
    },
  };
}

let defaultClient: CommandCenterClient | null = null;

export function getDefaultCommandCenterClient(): CommandCenterClient {
  if (!defaultClient) defaultClient = createCommandCenterClient();
  return defaultClient;
}

export function resetDefaultCommandCenterClient(): void {
  defaultClient = null;
  resetCommandCenterTestMode();
}
