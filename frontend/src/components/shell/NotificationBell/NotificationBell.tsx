import { SHELL_COPY } from '../../../shell/copy';
import shared from '../../../styles/shared.module.css';
import styles from './NotificationBell.module.css';

export interface NotificationBellProps {
  unreadCount?: number;
  placement?: 'default' | 'brand';
}

export function NotificationBell({ unreadCount = 0, placement = 'default' }: NotificationBellProps) {
  const hasUnread = unreadCount > 0;
  const label = hasUnread
    ? `${SHELL_COPY.notificationsLabel}, ${unreadCount} unread`
    : SHELL_COPY.notificationsLabel;

  return (
    <button
      type="button"
      className={[styles.bell, placement === 'brand' ? styles.bellBrand : '', shared.focusVisible]
        .filter(Boolean)
        .join(' ')}
      aria-label={label}
      data-notification-bell
      data-notification-unread-count={hasUnread ? unreadCount : undefined}
    >
      <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true" className={styles.icon}>
        <path
          d="M12 3a5 5 0 00-5 5v2.1c0 .9-.3 1.8-.9 2.5L4.7 15.5A1 1 0 005.5 17h13a1 1 0 00.7-1.7l-1.4-2.9a4.3 4.3 0 01-.9-2.5V8a5 5 0 00-5-5z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
        />
        <path d="M10 18a2 2 0 004 0" fill="none" stroke="currentColor" strokeWidth="1.75" />
      </svg>
      {hasUnread ? (
        <span className={styles.badge} aria-hidden="true">
          {unreadCount > 9 ? '9+' : unreadCount}
        </span>
      ) : null}
    </button>
  );
}
