export const CHANNELS_MIN_PAGE_SIZE = 6;
export const CHANNELS_MAX_PAGE_SIZE = 50;
export const CHANNELS_DEFAULT_PAGE_SIZE = 10;
export const CHANNELS_PAGE_SIZE_OPTIONS = [10, 25, 50] as const;

export function normalizeChannelsPageSize(pageSize?: number): number {
  const raw = pageSize ?? CHANNELS_DEFAULT_PAGE_SIZE;
  return Math.min(CHANNELS_MAX_PAGE_SIZE, Math.max(CHANNELS_MIN_PAGE_SIZE, raw));
}

export function isAllowedChannelsPageSize(pageSize: number): boolean {
  return (
    Number.isFinite(pageSize) &&
    pageSize >= CHANNELS_MIN_PAGE_SIZE &&
    pageSize <= CHANNELS_MAX_PAGE_SIZE &&
    Number.isInteger(pageSize)
  );
}
