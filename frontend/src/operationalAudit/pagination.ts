/** Default batch size for audit ledger cursor loads */
export const DEFAULT_PAGE_SIZE = 25;

/** Forensic/access ledger load-more batch (spec: 50) */
export const AUDIT_LEDGER_BATCH_SIZE = 50;

/** Maximum DOM tbody rows any Level 5 table may render in offset mode */
export const MAX_DOM_TABLE_ROWS = DEFAULT_PAGE_SIZE;

export interface PageWindow {
  pageSize: number;
  offset: number;
}

export interface CursorWindow {
  pageSize: number;
  cursor?: string;
}

export interface PageSlice<T> {
  rows: T[];
  totalCount: number;
  offset: number;
  pageSize: number;
  hasMore: boolean;
}

export interface CursorPageSlice<T> {
  rows: T[];
  totalCount: number;
  pageSize: number;
  hasMore: boolean;
  nextCursor?: string;
}

export function normalizePageWindow(window?: Partial<PageWindow>): PageWindow {
  const pageSize = Math.min(Math.max(window?.pageSize ?? DEFAULT_PAGE_SIZE, 1), MAX_DOM_TABLE_ROWS);
  const offset = Math.max(window?.offset ?? 0, 0);
  return { pageSize, offset };
}

export function normalizeCursorWindow(window?: Partial<CursorWindow>): CursorWindow {
  const pageSize = Math.max(window?.pageSize ?? AUDIT_LEDGER_BATCH_SIZE, 1);
  return { pageSize, cursor: window?.cursor };
}

export function formatAuditCursor(event: { occurredAt: string; eventId: string }): string {
  return `${event.occurredAt}|${event.eventId}`;
}

export function parseAuditCursor(cursor: string): { occurredAt: string; eventId: string } | undefined {
  const separator = cursor.indexOf('|');
  if (separator <= 0) return undefined;
  const occurredAt = cursor.slice(0, separator);
  const eventId = cursor.slice(separator + 1);
  if (!occurredAt || !eventId) return undefined;
  return { occurredAt, eventId };
}

function compareAuditEventsNewestFirst<T extends { occurredAt: string; eventId: string }>(
  a: T,
  b: T,
): number {
  const timeCmp = b.occurredAt.localeCompare(a.occurredAt);
  if (timeCmp !== 0) return timeCmp;
  return b.eventId.localeCompare(a.eventId);
}

export function sortAuditEventsNewestFirst<T extends { occurredAt: string; eventId: string }>(
  items: T[],
): T[] {
  return [...items].sort(compareAuditEventsNewestFirst);
}

export function slicePage<T>(items: T[], window?: Partial<PageWindow>): PageSlice<T> {
  const { pageSize, offset } = normalizePageWindow(window);
  const totalCount = items.length;
  const rows = items.slice(offset, offset + pageSize);
  return {
    rows,
    totalCount,
    offset,
    pageSize,
    hasMore: offset + rows.length < totalCount,
  };
}

export function sliceCursorPage<T extends { occurredAt: string; eventId: string }>(
  items: T[],
  window?: Partial<CursorWindow>,
): CursorPageSlice<T> {
  const { pageSize, cursor } = normalizeCursorWindow(window);
  const sorted = sortAuditEventsNewestFirst(items);
  const totalCount = sorted.length;

  let start = 0;
  if (cursor) {
    const parsed = parseAuditCursor(cursor);
    if (parsed) {
      const anchorIndex = sorted.findIndex(
        (item) => item.occurredAt === parsed.occurredAt && item.eventId === parsed.eventId,
      );
      start = anchorIndex >= 0 ? anchorIndex + 1 : sorted.length;
    }
  }

  const rows = sorted.slice(start, start + pageSize);
  const hasMore = start + rows.length < totalCount;
  const lastRow = rows[rows.length - 1];
  return {
    rows,
    totalCount,
    pageSize,
    hasMore,
    nextCursor: hasMore && lastRow ? formatAuditCursor(lastRow) : undefined,
  };
}

export function enforceDomRowCap<T>(rows: T[]): T[] {
  if (rows.length > MAX_DOM_TABLE_ROWS) {
    return rows.slice(0, MAX_DOM_TABLE_ROWS);
  }
  return rows;
}
