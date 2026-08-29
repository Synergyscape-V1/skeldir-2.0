import type { PolicyAuthorityState } from '../lib/types';
import { POLICY_AUTHORITY_STATES } from '../lib/types';
import { POLICY_AUTHORITY_UI_LABELS } from '../lib/policyAuthorityLabels';
import type { DiscrepancyClass } from '../ledger/types';
import type { ClaimsFilters } from './claimsClient';
import { dateRangeChipLabel } from './claimsDateRange';

export const CLAIM_SOURCE_LABELS: Record<string, string> = {
  meta_ads: 'Meta Ads',
  google_ads: 'Google Ads',
  tiktok_ads: 'TikTok Ads',
  linkedin_ads: 'LinkedIn Ads',
};

export const CAMPAIGN_CLASS_LABELS: Record<string, string> = {
  paid_search: 'Paid Search',
  paid_social: 'Paid Social',
  creator: 'Creator',
  branded: 'Branded',
  affiliate: 'Affiliate',
};

export const COMMERCE_RAIL_LABELS: Record<string, string> = {
  organic: 'Organic',
  organic_search: 'Organic Search',
  direct: 'Direct',
  referral: 'Referral',
  email: 'Email',
};

export const COMMERCE_TRUTH_SOURCE_LABELS: Record<string, string> = {
  shopify: 'Shopify',
  stripe: 'Stripe',
};

/** Commerce integration truth — not commerce rail. */
export const COMMERCE_SOURCE_LABELS = COMMERCE_TRUTH_SOURCE_LABELS;

export const VERIFICATION_STATUS_LABELS: Record<string, string> = {
  verified: 'Verified',
  partial: 'Partial',
  unverified: 'Unverified',
};

export const DISCREPANCY_CLASS_LABELS: Record<DiscrepancyClass, string> = {
  within_tolerance: 'Within tolerance',
  flagged: 'Flagged',
  material: 'Material',
  unknown: 'Unknown',
};

export const POLICY_AUTHORITY_LABELS = POLICY_AUTHORITY_UI_LABELS;

export const CLAIM_SORT_LABELS: Record<string, string> = {
  lastUpdated: 'Date',
  date: 'Claim time',
  discrepancy: 'Discrepancy',
  verificationStatus: 'Verification status',
};

export type ClaimsFilterChipKey =
  | 'dateRange'
  | 'claimSource'
  | 'campaignClass'
  | 'commerceRail'
  | 'commerceSource'
  | 'verificationStatus'
  | 'discrepancyClass'
  | 'policyAuthority'
  | 'search';

export interface ClaimsFilterChip {
  key: ClaimsFilterChipKey;
  label: string;
  /** Raw vendor/platform value used to resolve a brand mark, when applicable. */
  logoKey?: string;
}

export function hasActiveClaimsFilters(filters: ClaimsFilters): boolean {
  return Boolean(
    filters.dateFrom ||
      filters.dateTo ||
      filters.claimSource ||
      filters.campaignClass ||
      filters.commerceRail ||
      filters.commerceSource ||
      filters.verificationStatus ||
      filters.discrepancyClass ||
      filters.policyAuthority ||
      filters.search,
  );
}

export function buildActiveClaimsFilterChips(filters: ClaimsFilters): ClaimsFilterChip[] {
  const chips: ClaimsFilterChip[] = [];

  const dateLabel = dateRangeChipLabel(filters.dateFrom, filters.dateTo);
  if (dateLabel) {
    chips.push({ key: 'dateRange', label: dateLabel });
  }
  if (filters.claimSource) {
    chips.push({
      key: 'claimSource',
      label: CLAIM_SOURCE_LABELS[filters.claimSource] ?? filters.claimSource,
      logoKey: filters.claimSource,
    });
  }
  if (filters.campaignClass) {
    chips.push({
      key: 'campaignClass',
      label: CAMPAIGN_CLASS_LABELS[filters.campaignClass] ?? filters.campaignClass,
    });
  }
  if (filters.commerceRail) {
    chips.push({
      key: 'commerceRail',
      label: COMMERCE_RAIL_LABELS[filters.commerceRail] ?? filters.commerceRail,
    });
  }
  if (filters.commerceSource) {
    chips.push({
      key: 'commerceSource',
      label: COMMERCE_TRUTH_SOURCE_LABELS[filters.commerceSource] ?? filters.commerceSource,
      logoKey: filters.commerceSource,
    });
  }
  if (filters.verificationStatus) {
    chips.push({
      key: 'verificationStatus',
      label: VERIFICATION_STATUS_LABELS[filters.verificationStatus] ?? filters.verificationStatus,
    });
  }
  if (filters.discrepancyClass) {
    chips.push({
      key: 'discrepancyClass',
      label:
        DISCREPANCY_CLASS_LABELS[filters.discrepancyClass as DiscrepancyClass] ??
        filters.discrepancyClass,
    });
  }
  if (filters.policyAuthority) {
    chips.push({
      key: 'policyAuthority',
      label:
        POLICY_AUTHORITY_LABELS[filters.policyAuthority as PolicyAuthorityState] ??
        filters.policyAuthority,
    });
  }
  if (filters.search) {
    chips.push({ key: 'search', label: `Search: ${filters.search}` });
  }

  return chips;
}

export function clearClaimsFilterChip(
  filters: ClaimsFilters,
  chipKey: ClaimsFilterChipKey,
): ClaimsFilters {
  switch (chipKey) {
    case 'dateRange':
      return { ...filters, dateFrom: undefined, dateTo: undefined, offset: 0 };
    case 'claimSource':
      return { ...filters, claimSource: undefined, offset: 0 };
    case 'campaignClass':
      return { ...filters, campaignClass: undefined, offset: 0 };
    case 'commerceRail':
      return { ...filters, commerceRail: undefined, offset: 0 };
    case 'commerceSource':
      return { ...filters, commerceSource: undefined, offset: 0 };
    case 'verificationStatus':
      return { ...filters, verificationStatus: undefined, offset: 0 };
    case 'discrepancyClass':
      return { ...filters, discrepancyClass: undefined, offset: 0 };
    case 'policyAuthority':
      return { ...filters, policyAuthority: undefined, offset: 0 };
    case 'search':
      return { ...filters, search: undefined, offset: 0 };
    default:
      return filters;
  }
}

export { POLICY_AUTHORITY_STATES };
