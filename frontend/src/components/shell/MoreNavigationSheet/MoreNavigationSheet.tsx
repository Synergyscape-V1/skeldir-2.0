import type { RefObject } from 'react';
import { NavLink } from 'react-router-dom';
import { Drawer } from '../../layout/Drawer/Drawer';
import { SHELL_COPY } from '../../../shell/copy';
import { SHELL_NAV_ITEMS, isNavUnlocked, shellNavPath } from '../../../shell/navigation';
import type { ShellNavItemId } from '../../../shell/types';
import shared from '../../../styles/shared.module.css';
import navStyles from '../shellNav.module.css';
import styles from './MoreNavigationSheet.module.css';

export interface MoreNavigationSheetProps {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
  activeNavId?: ShellNavItemId | 'landing' | 'more' | 'onboarding' | 'integrations';
}

export function MoreNavigationSheet({ open, onClose, triggerRef, activeNavId }: MoreNavigationSheetProps) {
  return (
    <Drawer
      open={open}
      onClose={onClose}
      triggerRef={triggerRef}
      title={SHELL_COPY.moreNavTitle}
      position="right"
      allowEscape
    >
      <nav className={styles.nav} aria-label={SHELL_COPY.moreNavLabel} data-shell-more-sheet>
        <ul className={styles.list}>
          <li>
            <NavLink
              to="/app"
              end
              className={({ isActive }) =>
                [navStyles.navItem, shared.focusVisible, isActive || activeNavId === 'landing' ? navStyles.navItemActive : '']
                  .filter(Boolean)
                  .join(' ')
              }
              onClick={onClose}
            >
              <span className={navStyles.navItemLabel}>App frame</span>
            </NavLink>
          </li>
          {SHELL_NAV_ITEMS.map((item) => {
            const unlocked = isNavUnlocked(item.unlockLevel);
            return (
            <li key={item.id}>
              <NavLink
                to={shellNavPath(item.id)}
                className={({ isActive }) =>
                  [
                    navStyles.navItem,
                    unlocked ? '' : navStyles.navItemBlocked,
                    shared.focusVisible,
                    isActive || activeNavId === item.id ? navStyles.navItemActive : '',
                  ]
                    .filter(Boolean)
                    .join(' ')
                }
                onClick={onClose}
              >
                <span className={navStyles.navItemLabel}>{item.label}</span>
                {!unlocked ? <span className={navStyles.navItemMeta}>Blocked</span> : null}
              </NavLink>
            </li>
          );
          })}
        </ul>
      </nav>
    </Drawer>
  );
}
