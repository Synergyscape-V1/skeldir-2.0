import type { ReactNode } from 'react';
import { useState } from 'react';
import { LEDGER_COPY } from '../../../ledger/copy';
import shared from '../../../styles/shared.module.css';
import styles from './CompactLedgerRow.module.css';

export interface CompactLedgerField {
  key: string;
  label: string;
  value: ReactNode;
  primary?: boolean;
}

export interface CompactLedgerRowProps {
  rowKey: string;
  identity: ReactNode;
  status?: ReactNode;
  selectionControl?: ReactNode;
  primaryFields: CompactLedgerField[];
  secondaryFields: CompactLedgerField[];
}

export function CompactLedgerRow({
  rowKey,
  identity,
  status,
  selectionControl,
  primaryFields,
  secondaryFields,
}: CompactLedgerRowProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article
      className={styles.card}
      data-compact-ledger-row={rowKey}
      aria-label={`Ledger row ${rowKey}`}
    >
      <header className={styles.header}>
        {selectionControl ? <div className={styles.selection}>{selectionControl}</div> : null}
        <div className={styles.identity}>{identity}</div>
        {status ? <div className={styles.status}>{status}</div> : null}
      </header>
      <dl className={styles.primaryList}>
        {primaryFields.map((field) => (
          <div key={field.key} className={styles.field}>
            <dt>{field.label}</dt>
            <dd>{field.value}</dd>
          </div>
        ))}
      </dl>
      {secondaryFields.length > 0 ? (
        <>
          <button
            type="button"
            className={[styles.disclosure, shared.focusVisible].join(' ')}
            aria-expanded={expanded}
            aria-controls={`row-details-${rowKey}`}
            onClick={() => setExpanded((v) => !v)}
          >
            {LEDGER_COPY.mobileDisclosureLabel}
          </button>
          {expanded ? (
            <dl id={`row-details-${rowKey}`} className={styles.secondaryList}>
              {secondaryFields.map((field) => (
                <div key={field.key} className={styles.field}>
                  <dt>{field.label}</dt>
                  <dd>{field.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </>
      ) : null}
    </article>
  );
}

export function useCompactLedgerMode(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(max-width: 767px)').matches;
}
