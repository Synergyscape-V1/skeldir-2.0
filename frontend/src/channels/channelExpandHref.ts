/** UI-only deep-link key for Channel Overview inline expansion (not a data filter). */
export const CHANNELS_EXPAND_PARAM = 'expand';

export function readChannelExpandId(search: string): string | null {
  const raw = search.startsWith('?') ? search.slice(1) : search;
  const value = new URLSearchParams(raw).get(CHANNELS_EXPAND_PARAM);
  if (!value || value.trim().length === 0) return null;
  return value;
}

export function withChannelExpandParam(search: string, channelId: string | null): string {
  const raw = search.startsWith('?') ? search.slice(1) : search;
  const params = new URLSearchParams(raw);
  if (channelId && channelId.trim().length > 0) {
    params.set(CHANNELS_EXPAND_PARAM, channelId);
  } else {
    params.delete(CHANNELS_EXPAND_PARAM);
  }
  const next = params.toString();
  return next ? `?${next}` : '';
}

export function buildChannelExpandHref(channelId: string, currentSearch = ''): string {
  return `/app/channels${withChannelExpandParam(currentSearch, channelId)}`;
}

/** Preserve expand across filter/sort/pagination navigations that rebuild from ChannelsFilters. */
export function mergeExpandIntoSearch(search: string, expandChannelId: string | null): string {
  return withChannelExpandParam(search, expandChannelId);
}
