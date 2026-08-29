import closeNavbarIcon from '../../../assets/icons/nav/close_navbar.svg';
import openNavbarIcon from '../../../assets/icons/nav/open_navbar.svg';
import { SHELL_COPY } from '../../../shell/copy';
import shared from '../../../styles/shared.module.css';
import styles from './ChatToggle.module.css';

export interface ChatToggleProps {
  open: boolean;
  onToggle: () => void;
}

const ICON_SIZE = 16;

export function ChatToggle({ open, onToggle }: ChatToggleProps) {
  const label = open ? SHELL_COPY.chatToggleClose : SHELL_COPY.chatToggleOpen;
  const iconSrc = open ? openNavbarIcon : closeNavbarIcon;
  const iconIntent = open ? 'close' : 'open';

  return (
    <button
      type="button"
      className={[styles.toggle, shared.focusVisible].join(' ')}
      aria-label={label}
      aria-expanded={open}
      aria-controls="shell-chat-panel"
      data-chat-toggle
      data-chat-toggle-state={open ? 'open' : 'closed'}
      onClick={onToggle}
    >
      <img
        src={iconSrc}
        alt=""
        className={styles.icon}
        width={ICON_SIZE}
        height={ICON_SIZE}
        data-chat-toggle-icon={iconIntent}
        draggable={false}
      />
    </button>
  );
}
