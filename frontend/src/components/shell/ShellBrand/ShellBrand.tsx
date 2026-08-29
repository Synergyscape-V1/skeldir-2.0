import shieldMark from '../../../assets/icons/brand/shield-mark.svg';
import wordmarkSvg from '../../../assets/icons/brand/wordmark.svg';
import { NotificationBell } from '../NotificationBell/NotificationBell';
import styles from './ShellBrand.module.css';

const SHIELD_SIZE = 52;
const WORDMARK_HEIGHT = 24;
const WORDMARK_WIDTH = 102;

export function ShellBrand() {
  return (
    <div className={styles.brand} data-shell-brand aria-label="Skeldir">
      <div className={styles.lockup} data-shell-brand-lockup>
        <span className={styles.logoSlot}>
          <img
            src={shieldMark}
            alt=""
            className={styles.shield}
            width={SHIELD_SIZE}
            height={SHIELD_SIZE}
            data-shell-brand-shield
          />
        </span>
        <img
          src={wordmarkSvg}
          alt=""
          className={styles.wordmarkSvg}
          data-shell-brand-wordmark
          width={WORDMARK_WIDTH}
          height={WORDMARK_HEIGHT}
        />
      </div>
      <div className={styles.bellCorner} data-shell-brand-notification-corner>
        <NotificationBell unreadCount={3} placement="brand" />
      </div>
    </div>
  );
}
