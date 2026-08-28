import type { ReactNode } from 'react';
import styles from './ResponsiveShell.module.css';

export interface ResponsiveShellProps {
  sidebar?: ReactNode;
  trailing?: ReactNode;
  header?: ReactNode;
  children: ReactNode;
  viewportLabel?: string;
  /** When presentational, avoids nested landmark duplication in specimen galleries */
  landmarkMode?: 'semantic' | 'presentational';
}

export function ResponsiveShell({
  sidebar,
  trailing,
  header,
  children,
  viewportLabel,
  landmarkMode = 'semantic',
}: ResponsiveShellProps) {
  const HeaderTag = landmarkMode === 'semantic' ? 'header' : 'div';
  const SidebarTag = landmarkMode === 'semantic' ? 'aside' : 'div';
  const TrailingTag = landmarkMode === 'semantic' ? 'aside' : 'div';
  const MainTag = landmarkMode === 'semantic' ? 'main' : 'div';

  return (
    <div className={styles.shell} data-viewport={viewportLabel} data-responsive-shell>
      <div className={styles.body}>
        {sidebar ? (
          <SidebarTag
            className={styles.sidebar}
            data-shell-sidebar-column
            {...(landmarkMode === 'semantic' ? { 'aria-label': 'Sidebar primitive' } : {})}
          >
            {sidebar}
          </SidebarTag>
        ) : null}
        <div className={styles.mainColumn} data-shell-main-column>
          {header ? (
            <HeaderTag
              className={styles.header}
              data-shell-header-column
              {...(landmarkMode === 'semantic' ? { 'aria-label': 'Header primitive' } : {})}
            >
              {header}
            </HeaderTag>
          ) : null}
          <MainTag
            className={styles.main}
            {...(landmarkMode === 'semantic' ? { 'aria-label': 'Main content primitive' } : {})}
          >
            {children}
          </MainTag>
        </div>
        {trailing ? (
          <TrailingTag
            className={styles.trailing}
            data-shell-chat-column
            {...(landmarkMode === 'semantic' ? { 'aria-label': 'Workspace assistant panel' } : {})}
          >
            {trailing}
          </TrailingTag>
        ) : null}
      </div>
    </div>
  );
}
