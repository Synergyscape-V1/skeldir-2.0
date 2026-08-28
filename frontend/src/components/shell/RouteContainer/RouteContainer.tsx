import type { ReactNode } from 'react';
import styles from './RouteContainer.module.css';

export interface RouteContainerProps {
  children: ReactNode;
  pageTitle?: string;
}

export function RouteContainer({ children, pageTitle }: RouteContainerProps) {
  return (
    <div className={styles.container} data-shell-route-container>
      <div className={styles.content} data-shell-route-content>
        {pageTitle ? <h2 className={styles.srTitle}>{pageTitle}</h2> : null}
        {children}
      </div>
    </div>
  );
}
