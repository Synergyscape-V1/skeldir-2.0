type RelativeTimeUnitStyle = 'full' | 'compact';

function formatRelativeTimeValue(iso: string, now: number, unitStyle: RelativeTimeUnitStyle): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'recently';
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return 'just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) {
    const unit = unitStyle === 'compact' ? 'min' : `minute${diffMin === 1 ? '' : 's'}`;
    return `${diffMin} ${unit} ago`;
  }
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) {
    const unit = unitStyle === 'compact' ? 'hr' : `hour${diffHr === 1 ? '' : 's'}`;
    return `${diffHr} ${unit} ago`;
  }
  const diffDay = Math.floor(diffHr / 24);
  const unit = unitStyle === 'compact' ? 'd' : `day${diffDay === 1 ? '' : 's'}`;
  return `${diffDay} ${unit} ago`;
}

export function formatRelativeTimeShort(iso: string, now = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return 'now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d`;
}

export function formatRelativeTime(iso: string, now = Date.now()): string {
  return formatRelativeTimeValue(iso, now, 'full');
}

export function formatRelativeTimeCompact(iso: string, now = Date.now()): string {
  return formatRelativeTimeValue(iso, now, 'compact');
}

export function formatRelativeUpdatedTime(iso: string, now = Date.now()): string {
  const relative = formatRelativeTime(iso, now);
  if (relative === 'recently') return 'Updated recently';
  if (relative === 'just now') return 'Updated just now';
  return `Updated ${relative}`;
}
