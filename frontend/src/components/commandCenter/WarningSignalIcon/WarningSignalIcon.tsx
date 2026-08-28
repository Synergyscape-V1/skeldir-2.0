import type { HTMLAttributes } from 'react';
import styles from './WarningSignalIcon.module.css';

/** Geometry from `src/assets/icons/nav/warning.svg` — inline for currentColor theming. */
export function WarningSignalIcon({
  className,
  style,
  ...rest
}: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={[styles.root, className].filter(Boolean).join(' ')}
      style={style}
      aria-hidden="true"
      {...rest}
    >
      <svg className={styles.icon} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M15.12 4.623a1 1 0 011.76 0l11.32 20.9A1 1 0 0127.321 27H4.679a1 1 0 01-.88-1.476l11.322-20.9zM16 18v-6"
        />
        <path fill="currentColor" d="M17.5 22.5a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
      </svg>
    </span>
  );
}
