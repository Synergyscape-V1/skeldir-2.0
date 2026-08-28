import type { ReactNode } from 'react';
import shared from '../../../styles/shared.module.css';
import styles from './CollapsibleSection.module.css';

export interface CollapsibleSectionProps {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  dataAttribute?: string;
}

export function CollapsibleSection({
  summary,
  children,
  defaultOpen = false,
  className,
  dataAttribute,
}: CollapsibleSectionProps) {
  return (
    <details
      className={[styles.root, className].filter(Boolean).join(' ')}
      open={defaultOpen ? true : undefined}
      {...(dataAttribute ? { [`data-${dataAttribute}`]: true } : {})}
    >
      <summary className={[styles.summary, shared.focusVisible].join(' ')}>{summary}</summary>
      <div className={styles.content}>{children}</div>
    </details>
  );
}
