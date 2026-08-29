import type { ReactNode } from 'react';
import { AUTH_COPY } from '../../../auth/copy';
import { AuthBrand } from '../AuthBrand/AuthBrand';
import shared from '../../../styles/shared.module.css';
import styles from './AuthEntryCanvas.module.css';

export interface AuthEntryCanvasProps {
  children: ReactNode;
  showBrand?: boolean;
  dataRoute?: string;
}

export function AuthEntryCanvas({ children, showBrand = true, dataRoute }: AuthEntryCanvasProps) {
  return (
    <div className={styles.canvas} data-route={dataRoute}>
      <div className={styles.inner}>
        <div className={styles.card} data-auth-entry-card>
          {showBrand ? <AuthBrand /> : null}
          {children}
        </div>
        <p className={styles.supportFooter} data-auth-support-footer>
          {AUTH_COPY.supportFooterPrefix}{' '}
          <a
            href={`mailto:${AUTH_COPY.supportEmail}`}
            className={[styles.supportLink, shared.focusVisible].join(' ')}
          >
            {AUTH_COPY.supportEmail}
          </a>
        </p>
      </div>
    </div>
  );
}
