import closeNavbarIcon from '../../../assets/icons/nav/close_navbar.svg';
import openNavbarIcon from '../../../assets/icons/nav/open_navbar.svg';
import { SHELL_COPY } from '../../../shell/copy';
import shared from '../../../styles/shared.module.css';
import styles from './SidebarToggle.module.css';

export interface SidebarToggleProps {
  collapsed: boolean;
  onToggle: () => void;
}

const ICON_SIZE = 16;

export function SidebarToggle({ collapsed, onToggle }: SidebarToggleProps) {
  const label = collapsed ? SHELL_COPY.sidebarToggleExpand : SHELL_COPY.sidebarToggleCollapse;
  const iconSrc = collapsed ? openNavbarIcon : closeNavbarIcon;
  const iconIntent = collapsed ? 'open' : 'close';

  return (
    <button
      type="button"
      className={[styles.toggle, shared.focusVisible].join(' ')}
      aria-label={label}
      aria-expanded={!collapsed}
      aria-controls="shell-sidebar-navigation"
      data-sidebar-toggle
      data-sidebar-toggle-state={collapsed ? 'collapsed' : 'expanded'}
      onClick={onToggle}
    >
      <img
        src={iconSrc}
        alt=""
        className={styles.icon}
        width={ICON_SIZE}
        height={ICON_SIZE}
        data-sidebar-toggle-icon={iconIntent}
        draggable={false}
      />
    </button>
  );
}
