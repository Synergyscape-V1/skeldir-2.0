import { useRef, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { SHELL_COPY } from '../../../shell/copy';
import { MOBILE_PRIMARY_NAV_IDS, SHELL_NAV_ITEMS, shellNavPath } from '../../../shell/navigation';
import type { ShellNavItemId } from '../../../shell/types';
import { NavIcon } from '../../icons/NavIcon';
import shared from '../../../styles/shared.module.css';
import { MoreNavigationSheet } from '../MoreNavigationSheet/MoreNavigationSheet';
import styles from './MobileBottomNavigation.module.css';

export interface MobileBottomNavigationProps {
  activeNavId?: ShellNavItemId | 'landing' | 'more' | 'onboarding' | 'integrations';
  moreSheetOpen?: boolean;
  onMoreSheetChange?: (open: boolean) => void;
}

export function MobileBottomNavigation({
  activeNavId,
  moreSheetOpen,
  onMoreSheetChange,
}: MobileBottomNavigationProps) {
  const [internalMoreOpen, setInternalMoreOpen] = useState(false);
  const moreOpen = moreSheetOpen ?? internalMoreOpen;
  const setMoreOpen = onMoreSheetChange ?? setInternalMoreOpen;
  const moreTriggerRef = useRef<HTMLButtonElement>(null);

  const primaryItems = SHELL_NAV_ITEMS.filter((item) => MOBILE_PRIMARY_NAV_IDS.includes(item.id));

  return (
    <>
      <nav className={styles.bottomNav} aria-label={SHELL_COPY.bottomNavLabel} data-shell-bottom-nav>
        {primaryItems.map((item) => (
          <NavLink
            key={item.id}
            to={shellNavPath(item.id)}
            className={({ isActive }) =>
              [styles.bottomItem, shared.focusVisible, isActive || activeNavId === item.id ? styles.bottomItemActive : '']
                .filter(Boolean)
                .join(' ')
            }
          >
            <NavIcon navId={item.id} active={activeNavId === item.id} />
            <span className={styles.bottomLabel}>{item.label.split(' ')[0]}</span>
          </NavLink>
        ))}
        <button
          ref={moreTriggerRef}
          type="button"
          className={[styles.bottomItem, shared.focusVisible, moreOpen || activeNavId === 'more' ? styles.bottomItemActive : '']
            .filter(Boolean)
            .join(' ')}
          aria-label={SHELL_COPY.moreNavLabel}
          aria-expanded={moreOpen}
          aria-haspopup="dialog"
          onClick={() => setMoreOpen(true)}
        >
          <NavIcon navId="settings" />
          <span className={styles.bottomLabel}>More</span>
        </button>
      </nav>
      <MoreNavigationSheet
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        triggerRef={moreTriggerRef}
        activeNavId={activeNavId}
      />
    </>
  );
}
