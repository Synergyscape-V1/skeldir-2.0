import type { ShellNavItemId } from '../../shell/types';
import { NAV_ICON_SRC } from './navIconMap';
import styles from './NavIcon.module.css';

export interface NavIconProps {
  navId: ShellNavItemId | 'command-center';
  active?: boolean;
}

export function NavIcon({ navId, active }: NavIconProps) {
  const src = NAV_ICON_SRC[navId];
  return (
    <span className={[styles.slot, active ? styles.active : ''].filter(Boolean).join(' ')} aria-hidden="true">
      <img src={src} alt="" className={styles.icon} width={20} height={20} />
    </span>
  );
}
