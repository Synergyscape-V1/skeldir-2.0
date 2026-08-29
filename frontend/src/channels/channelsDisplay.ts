import { claimSourceLabel } from '../claims/claimsLedgerDisplay';
import type { ChannelOverviewRowDTO } from '../ledger/types';
import { ATTRIBUTION_CHANNEL_LABELS, CHANNEL_FILTER_LABELS } from './channelsFilterConfig';

export { ATTRIBUTION_CHANNEL_LABELS } from './channelsFilterConfig';
export { buildChannelCompositeId, isValidChannelCompositeId } from './channelIds';

export function attributionChannelLabel(attributionChannel: string): string {
  return ATTRIBUTION_CHANNEL_LABELS[attributionChannel as keyof typeof ATTRIBUTION_CHANNEL_LABELS] ??
    attributionChannel.replace(/_/g, ' ');
}

export function channelsClaimSourceLabel(claimSource: string): string {
  return (
    CHANNEL_FILTER_LABELS.claimSource[claimSource as keyof typeof CHANNEL_FILTER_LABELS.claimSource] ??
    claimSourceLabel(claimSource)
  );
}

export function channelRowIdentityLabel(row: Pick<ChannelOverviewRowDTO, 'channelName' | 'claimSource'>): string {
  return `${row.channelName} · ${channelsClaimSourceLabel(row.claimSource)}`;
}
