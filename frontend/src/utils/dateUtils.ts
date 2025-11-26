/**
 * Format a date/timestamp to relative time format
 * Examples: "just now", "2 mins ago", "3 hours ago", "2 days ago"
 */
export function formatRelativeTime(timestamp: string | Date): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 10) {
    return 'just now';
  } else if (diffSec < 60) {
    return `${diffSec} secs ago`;
  } else if (diffMin === 1) {
    return '1 min ago';
  } else if (diffMin < 60) {
    return `${diffMin} mins ago`;
  } else if (diffHour === 1) {
    return '1 hour ago';
  } else if (diffHour < 24) {
    return `${diffHour} hours ago`;
  } else if (diffDay === 1) {
    return '1 day ago';
  } else if (diffDay < 7) {
    return `${diffDay} days ago`;
  } else {
    // For dates older than a week, show the actual date
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    });
  }
}
