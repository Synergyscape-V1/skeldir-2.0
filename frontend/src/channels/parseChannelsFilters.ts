import type { ChannelsFilters } from './channelsClient';
import { buildChannelsQueryKey, parseCanonicalChannelsQuery } from './channelsQueryState';

export function parseChannelsFilters(search: string): ChannelsFilters {
  return parseCanonicalChannelsQuery(search).filters;
}

export { buildChannelsQueryKey };
