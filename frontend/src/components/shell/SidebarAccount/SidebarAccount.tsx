import { useEffect, useId, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clearSession, getAuthState, subscribeAuthState } from '../../../auth/sessionStore';
import type { ProductAuthState } from '../../../auth/sessionStore';
import { deriveUserInitials, resolveSidebarAccountUser } from '../../../auth/userProfile';
import { SHELL_COPY } from '../../../shell/copy';
import shared from '../../../styles/shared.module.css';
import styles from './SidebarAccount.module.css';

export function SidebarAccount() {
  const navigate = useNavigate();
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [authState, setAuthState] = useState<ProductAuthState>(getAuthState);

  useEffect(() => subscribeAuthState(setAuthState), []);

  useEffect(() => {
    if (!menuOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen]);

  const user = resolveSidebarAccountUser(authState);
  if (!user) {
    return null;
  }

  const initials = deriveUserInitials(user.firstName, user.lastName);

  const handleLogout = () => {
    setMenuOpen(false);
    clearSession();
    navigate('/login', { replace: true });
  };

  return (
    <div className={styles.root} ref={rootRef} data-shell-sidebar-account>
      <button
        type="button"
        className={[styles.trigger, shared.focusVisible].join(' ')}
        aria-label={SHELL_COPY.accountMenuLabel}
        aria-expanded={menuOpen}
        aria-haspopup="menu"
        aria-controls={menuId}
        onClick={() => setMenuOpen((open) => !open)}
      >
        <span className={styles.avatar} aria-label={SHELL_COPY.accountInitialsLabel(initials)}>
          {initials}
        </span>
        <span className={styles.email}>{user.email}</span>
      </button>

      {menuOpen ? (
        <div
          id={menuId}
          role="menu"
          className={styles.menu}
          aria-label={SHELL_COPY.accountMenuLabel}
          data-shell-sidebar-account-menu
        >
          <button
            type="button"
            role="menuitem"
            className={[styles.menuItem, shared.focusVisible].join(' ')}
            onClick={handleLogout}
          >
            {SHELL_COPY.accountMenuLogout}
          </button>
        </div>
      ) : null}
    </div>
  );
}
