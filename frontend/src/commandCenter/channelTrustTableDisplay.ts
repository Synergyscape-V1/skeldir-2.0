import { channelTrustAxisHeader } from './channelTrustDisplay';
import { COMMAND_CENTER_COPY } from './copy';
import type { ChannelTrustGroupBy } from './types';

const COL = COMMAND_CENTER_COPY.channelTableColumns;

export type ChannelTrustTableHeaderKey =
  | 'axis'
  | 'verifiedRevenue'
  | 'discrepancyRate'
  | 'revenueReliability'
  | 'policyAuthority';

export function channelTrustTableHeaderKeys(_groupBy: ChannelTrustGroupBy): ChannelTrustTableHeaderKey[] {
  return ['axis', 'verifiedRevenue', 'discrepancyRate', 'revenueReliability', 'policyAuthority'];
}

export function channelTrustTableHeaderLabel(
  key: ChannelTrustTableHeaderKey,
  groupBy: ChannelTrustGroupBy,
): string {
  switch (key) {
    case 'axis':
      return channelTrustAxisHeader(groupBy);
    case 'verifiedRevenue':
      return COL.verifiedRevenue;
    case 'discrepancyRate':
      return COL.discrepancyRate;
    case 'revenueReliability':
      return COL.revenueReliability;
    case 'policyAuthority':
      return COL.policyAuthority;
    default:
      return '';
  }
}
