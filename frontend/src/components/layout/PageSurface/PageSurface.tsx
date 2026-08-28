import type { HTMLAttributes, ReactNode } from 'react';
import styles from './PageSurface.module.css';

export interface PageSurfaceProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function PageSurface({ children, className, ...rest }: PageSurfaceProps) {
  return (
    <div className={[styles.page, className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </div>
  );
}
