const CHANNEL_COMPOSITE_ID_PATTERN = /^ch_[a-z0-9_]+__[a-z0-9_]+$/;

export function buildChannelCompositeId(attributionChannel: string, claimSource: string): string {
  return `ch_${attributionChannel}__${claimSource}`;
}

export function isValidChannelCompositeId(channelId: string): boolean {
  return CHANNEL_COMPOSITE_ID_PATTERN.test(channelId);
}
