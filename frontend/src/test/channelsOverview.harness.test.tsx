import { describe, expect, it } from 'vitest';
import { computeChannelOverviewSummary } from '../channels/channelsSummary';
import { CHANNELS_OVERVIEW_FIXTURES } from '../channels/channelsFixtures';
import {
  channelsFiltersToSearchParams,
  parseCanonicalChannelsQuery,
} from '../channels/channelsQueryState';
import { createChannelsClient } from '../channels/channelsClient';
import { channelRowIdentityLabel } from '../channels/channelsDisplay';

describe('Channels overview data layer', () => {
  it('fixture exposes six distinct attribution × claim-source intersections', async () => {
    expect(CHANNELS_OVERVIEW_FIXTURES).toHaveLength(6);
    const intersections = new Set(
      CHANNELS_OVERVIEW_FIXTURES.map((row) => `${row.attributionChannel}::${row.claimSource}`),
    );
    expect(intersections.size).toBe(6);
    expect(CHANNELS_OVERVIEW_FIXTURES.every((row) => row.verifiedRevenueMinor > 1_000_000n)).toBe(true);
    expect(CHANNELS_OVERVIEW_FIXTURES.some((row) => row.channelName === 'Paid Search' && row.claimSource === 'google_ads')).toBe(
      true,
    );
    expect(CHANNELS_OVERVIEW_FIXTURES.some((row) => row.channelName === 'Paid Social' && row.claimSource === 'meta_ads')).toBe(
      true,
    );
  });

  it('summary row identifies highest revenue, largest discrepancy, lowest confidence, and action-ready channel', () => {
    const summary = computeChannelOverviewSummary(CHANNELS_OVERVIEW_FIXTURES);
    expect(summary.highestVerifiedRevenueChannelName).toBe('Email / Lifecycle · Email');
    expect(summary.largestDiscrepancyChannelName).toBe('Paid Social · Meta Ads');
    expect(summary.lowestConfidenceChannelName).toBe('Creator Partnerships · Meta Ads');
    expect(summary.bestActionReadyChannelName).toBe('Paid Search · Google Ads');
    expect(summary.bestActionReadyPolicyAuthority).toBe('approval_required');
  });

  it('client returns paginated table rows with policy and benchmark fields', async () => {
    const client = createChannelsClient();
    const outcome = await client.listChannels('tenant_1', { pageSize: 10, offset: 0 });
    expect(outcome.kind).toBe('loaded');
    if (outcome.kind !== 'loaded') return;
    expect(outcome.rows).toHaveLength(6);
    expect(outcome.totalCount).toBe(6);
    expect(outcome.summary?.highestVerifiedRevenueChannelName).toBe('Email / Lifecycle · Email');
    const paidSearch = outcome.rows.find((row) => row.attributionChannel === 'paid_search');
    expect(paidSearch?.policyAuthority).toBe('approval_required');
    expect(paidSearch?.attributionModelAgreement).toBe('96.2%');
    expect(paidSearch?.claimSource).toBe('google_ads');
  });

  it('canonical query parser defaults metric basis to verified', () => {
    const parsed = parseCanonicalChannelsQuery('');
    expect(parsed.filters.metricBasis).toBe('verified');
    expect(parsed.isCanonical).toBe(true);
  });

  it('canonical query parser rejects invalid sort keys and rewrites URL', () => {
    const parsed = parseCanonicalChannelsQuery('?sortKey=not_a_real_key&sortDirection=desc');
    expect(parsed.filters.sortKey).toBe('policyAuthority');
    expect(parsed.isCanonical).toBe(false);
    expect(parsed.canonicalSearch).toContain('sortKey=policyAuthority');
  });

  it('filters serialize to canonical search params', () => {
    const params = channelsFiltersToSearchParams({
      attributionChannel: 'paid_search',
      metricBasis: 'platform_claim',
      sortKey: 'verifiedRevenue',
      sortDirection: 'desc',
      offset: 0,
      pageSize: 25,
    });
    expect(params.get('attributionChannel')).toBe('paid_search');
    expect(params.get('metricBasis')).toBe('platform_claim');
    expect(params.get('sortKey')).toBe('verifiedRevenue');
    expect(params.get('sortDirection')).toBe('desc');
  });

  it('attribution agreement filter uses integer basis points only', async () => {
    const client = createChannelsClient();
    const under90 = await client.listChannels('tenant_1', { attributionAgreement: 'under_90', pageSize: 25 });
    expect(under90.kind).toBe('loaded');
    if (under90.kind !== 'loaded') return;
    expect(under90.rows.every((row) => row.attributionModelAgreement !== '96.2%')).toBe(true);
    expect(under90.rows.some((row) => row.attributionChannel === 'paid_social')).toBe(true);
  });

  it('verified revenue sort orders rows deterministically', async () => {
    const client = createChannelsClient();
    const outcome = await client.listChannels('tenant_1', {
      sortKey: 'verifiedRevenue',
      sortDirection: 'desc',
      pageSize: 25,
    });
    expect(outcome.kind).toBe('loaded');
    if (outcome.kind !== 'loaded') return;
    const revenues = outcome.rows.map((row) => row.verifiedRevenueMinor);
    const sorted = [...revenues].sort((a, b) => (a < b ? 1 : a > b ? -1 : 0));
    expect(revenues).toEqual(sorted);
    expect(outcome.rows[0]?.channelName).toBe('Email / Lifecycle');
  });

  it('claim source and attribution channel dimensions remain independently filterable', async () => {
    const client = createChannelsClient();
    const metaOnly = await client.listChannels('tenant_1', { claimSource: 'meta_ads', pageSize: 25 });
    expect(metaOnly.kind).toBe('loaded');
    if (metaOnly.kind !== 'loaded') return;
    expect(metaOnly.rows.length).toBeGreaterThan(1);
    expect(metaOnly.rows.every((row) => row.claimSource === 'meta_ads')).toBe(true);
    expect(new Set(metaOnly.rows.map((row) => row.attributionChannel)).size).toBeGreaterThan(1);

    const paidSearchOnly = await client.listChannels('tenant_1', {
      attributionChannel: 'paid_search',
      pageSize: 25,
    });
    expect(paidSearchOnly.kind).toBe('loaded');
    if (paidSearchOnly.kind !== 'loaded') return;
    expect(paidSearchOnly.rows).toHaveLength(1);
    expect(channelRowIdentityLabel(paidSearchOnly.rows[0]!)).toBe('Paid Search · Google Ads');
  });

  it('attribution channel and claim source sort keys are accepted by query engine', async () => {
    const client = createChannelsClient();

    const byAttribution = await client.listChannels('tenant_1', {
      sortKey: 'attributionChannel',
      sortDirection: 'asc',
      pageSize: 25,
    });
    expect(byAttribution.kind).toBe('loaded');
    if (byAttribution.kind !== 'loaded') return;
    const attributionKeys = byAttribution.rows.map((row) => row.attributionChannel);
    const attributionSorted = [...attributionKeys].sort((a, b) => a.localeCompare(b));
    expect(attributionKeys).toEqual(attributionSorted);

    const byClaimSource = await client.listChannels('tenant_1', {
      sortKey: 'claimSource',
      sortDirection: 'asc',
      pageSize: 25,
    });
    expect(byClaimSource.kind).toBe('loaded');
    if (byClaimSource.kind !== 'loaded') return;
    const claimSources = byClaimSource.rows.map((row) => row.claimSource);
    const claimSorted = [...claimSources].sort((a, b) => a.localeCompare(b));
    expect(claimSources).toEqual(claimSorted);
  });

  it('every fixture row exposes policy authority for table pills', () => {
    expect(CHANNELS_OVERVIEW_FIXTURES.every((row) => row.policyAuthority.length > 0)).toBe(true);
    expect(new Set(CHANNELS_OVERVIEW_FIXTURES.map((row) => row.policyAuthority)).size).toBeGreaterThan(1);
  });
});
