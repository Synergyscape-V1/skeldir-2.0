import type { PolicyAuthorityState } from '../lib/types';
import { POLICY_AUTHORITY_STATES } from '../lib/types';
import { POLICY_AUTHORITY_UI_LABELS } from '../lib/policyAuthorityLabels';
import type { ChannelsFilters } from './channelsClient';
import { dateRangeChipLabel } from '../claims/claimsDateRange';

export const ATTRIBUTION_CHANNEL_LABELS = {
  paid_search: 'Paid Search',
  paid_social: 'Paid Social',
  organic_search: 'Organic Search',
  creator: 'Creator Partnerships',
  email_lifecycle: 'Email / Lifecycle',
  affiliate: 'Affiliate',
} as const;

export const CHANNEL_FILTER_LABELS = {
  attributionChannel: ATTRIBUTION_CHANNEL_LABELS,
  claimSource: {
    google_ads: 'Google Ads',
    meta_ads: 'Meta Ads',
    email: 'Email',
    organic_search: 'Organic Search',
    affiliate: 'Affiliate',
  },
  commerceSource: {
    shopify: 'Shopify',
    stripe: 'Stripe',
    woocommerce: 'WooCommerce',
    paypal: 'PayPal',
  },
  attributionAgreement: {
    under_90: 'Under 90%',
    under_80: 'Under 80%',
    all: 'All',
  },
  bayesianStatus: {
    needs_review: 'Needs review',
    healthy: 'Healthy',
    unavailable: 'Unavailable',
    degraded: 'Degraded',
  },
  benchmarkStatus: {
    attention_needed: 'Attention needed',
    stable: 'Stable',
    transitioning: 'Transitioning',
    unavailable: 'Unavailable',
  },
  actionAuthority: {
    actionable_only: 'Actionable only',
    approval_required: POLICY_AUTHORITY_UI_LABELS.approval_required,
    proposal_required: POLICY_AUTHORITY_UI_LABELS.proposal_required,
    simulation_only: POLICY_AUTHORITY_UI_LABELS.simulation_only,
    blocked: POLICY_AUTHORITY_UI_LABELS.blocked,
  },
} as const;

export const POLICY_AUTHORITY_LABELS = POLICY_AUTHORITY_UI_LABELS;

export type ChannelsFilterChipKey =
  | 'dateRange'
  | 'attributionChannel'
  | 'claimSource'  | 'commerceSource'
  | 'attributionAgreement'
  | 'bayesianStatus'
  | 'benchmarkStatus'
  | 'actionAuthority'
  | 'search';

export interface ChannelsFilterChip {
  key: ChannelsFilterChipKey;
  label: string;
}

export function hasActiveChannelsFilters(filters: ChannelsFilters): boolean {
  return Boolean(
    filters.dateFrom ||
      filters.dateTo ||
      filters.channelId ||
      filters.attributionChannel ||
      filters.claimSource ||
      filters.commerceSource ||
      filters.attributionAgreement ||
      filters.bayesianStatus ||
      filters.benchmarkStatus ||
      filters.actionAuthority ||
      filters.search,
  );
}

export function buildActiveChannelsFilterChips(filters: ChannelsFilters): ChannelsFilterChip[] {
  const chips: ChannelsFilterChip[] = [];
  const dateLabel = dateRangeChipLabel(filters.dateFrom, filters.dateTo);
  if (dateLabel) chips.push({ key: 'dateRange', label: dateLabel });
  if (filters.attributionChannel) {
    chips.push({
      key: 'attributionChannel',
      label:
        CHANNEL_FILTER_LABELS.attributionChannel[
          filters.attributionChannel as keyof typeof CHANNEL_FILTER_LABELS.attributionChannel
        ] ?? filters.attributionChannel,
    });
  }
  if (filters.channelId) {
    chips.push({
      key: 'attributionChannel',
      label: `Channel: ${filters.channelId}`,
    });
  }  if (filters.claimSource) {
    chips.push({
      key: 'claimSource',
      label: CHANNEL_FILTER_LABELS.claimSource[filters.claimSource as keyof typeof CHANNEL_FILTER_LABELS.claimSource] ?? filters.claimSource,
    });
  }
  if (filters.commerceSource) {
    chips.push({
      key: 'commerceSource',
      label:
        CHANNEL_FILTER_LABELS.commerceSource[filters.commerceSource as keyof typeof CHANNEL_FILTER_LABELS.commerceSource] ??
        filters.commerceSource,
    });
  }
  if (filters.attributionAgreement && filters.attributionAgreement !== 'all') {
    chips.push({
      key: 'attributionAgreement',
      label: `Revenue reliability ${CHANNEL_FILTER_LABELS.attributionAgreement[filters.attributionAgreement as keyof typeof CHANNEL_FILTER_LABELS.attributionAgreement] ?? filters.attributionAgreement}`,
    });
  }
  if (filters.bayesianStatus) {
    chips.push({
      key: 'bayesianStatus',
      label: `Bayesian: ${CHANNEL_FILTER_LABELS.bayesianStatus[filters.bayesianStatus as keyof typeof CHANNEL_FILTER_LABELS.bayesianStatus] ?? filters.bayesianStatus}`,
    });
  }
  if (filters.benchmarkStatus) {
    chips.push({
      key: 'benchmarkStatus',
      label: `Benchmark: ${CHANNEL_FILTER_LABELS.benchmarkStatus[filters.benchmarkStatus as keyof typeof CHANNEL_FILTER_LABELS.benchmarkStatus] ?? filters.benchmarkStatus}`,
    });
  }
  if (filters.actionAuthority) {
    chips.push({
      key: 'actionAuthority',
      label:
        filters.actionAuthority === 'actionable_only'
          ? 'Actionable only'
          : POLICY_AUTHORITY_LABELS[filters.actionAuthority as PolicyAuthorityState] ?? filters.actionAuthority,
    });
  }
  if (filters.search) chips.push({ key: 'search', label: `Search: ${filters.search}` });
  return chips;
}

export function clearChannelsFilterChip(
  filters: ChannelsFilters,
  chipKey: ChannelsFilterChipKey,
): ChannelsFilters {
  switch (chipKey) {
    case 'dateRange':
      return { ...filters, dateFrom: undefined, dateTo: undefined, offset: 0 };
    case 'attributionChannel':
      return { ...filters, attributionChannel: undefined, channelId: undefined, offset: 0 };    case 'claimSource':
      return { ...filters, claimSource: undefined, offset: 0 };
    case 'commerceSource':
      return { ...filters, commerceSource: undefined, offset: 0 };
    case 'attributionAgreement':
      return { ...filters, attributionAgreement: undefined, offset: 0 };
    case 'bayesianStatus':
      return { ...filters, bayesianStatus: undefined, offset: 0 };
    case 'benchmarkStatus':
      return { ...filters, benchmarkStatus: undefined, offset: 0 };
    case 'actionAuthority':
      return { ...filters, actionAuthority: undefined, offset: 0 };
    case 'search':
      return { ...filters, search: undefined, offset: 0 };
    default:
      return filters;
  }
}

export { POLICY_AUTHORITY_STATES };
