import { NavLink } from 'react-router-dom';
import { NavIcon } from '../../icons/NavIcon';
import { SHELL_COPY } from '../../../shell/copy';
import { SHELL_NAV_ITEMS, isNavUnlocked, shellNavPath, SHELL_NAV_SECTION_DIVIDERS_AFTER } from '../../../shell/navigation';
import type { ShellNavItemId } from '../../../shell/types';
import shared from '../../../styles/shared.module.css';
import { ShellBrand } from '../ShellBrand/ShellBrand';
import { SidebarAccount } from '../SidebarAccount/SidebarAccount';
import navStyles from '../shellNav.module.css';
import styles from './SidebarNavigation.module.css';

export interface SidebarNavigationProps {
  activeNavId?: ShellNavItemId | 'landing' | 'onboarding' | 'integrations';
}

export function SidebarNavigation({ activeNavId = 'command-center' }: SidebarNavigationProps) {
  const sectionDividerAfter = new Set(SHELL_NAV_SECTION_DIVIDERS_AFTER);

  return (
    <nav className={styles.nav} aria-label={SHELL_COPY.sidebarLabel} data-shell-sidebar id="shell-sidebar-navigation">
      <ShellBrand />
      <ul className={styles.list}>
        {SHELL_NAV_ITEMS.map((item) => {
          const unlocked = isNavUnlocked(item.unlockLevel);
          const isActive = activeNavId === item.id;
          return (
            <li
              key={item.id}
              className={sectionDividerAfter.has(item.id) ? styles.listItemWithSectionDivider : undefined}
            >
              <NavLink
                to={shellNavPath(item.id)}
                end={item.id === 'command-center'}
                className={({ isActive: routeActive }) =>
                  [
                    navStyles.navItem,
                    unlocked ? '' : navStyles.navItemBlocked,
                    shared.focusVisible,
                    routeActive || isActive ? navStyles.navItemActive : '',
                  ]
                    .filter(Boolean)
                    .join(' ')
                }
                aria-current={isActive ? 'page' : undefined}
                aria-disabled={unlocked ? undefined : true}
                data-nav-item={item.id}
              >
                <NavIcon navId={item.id} active={isActive} />
                <span className={navStyles.navItemLabel}>{item.label}</span>
                {!unlocked ? <span className={navStyles.navItemMeta}>Blocked</span> : null}
              </NavLink>
            </li>
          );
        })}
      </ul>
      <SidebarAccount />
    </nav>
  );
}

