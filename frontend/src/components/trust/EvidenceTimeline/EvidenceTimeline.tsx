import { ERROR_COPY } from '../../../lib/copy';
import type { EvidenceTimelineItem } from '../../../lib/types';
import { IconCopy } from '../../icons/StatusIcons';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { Skeleton } from '../../layout/Skeleton/Skeleton';
import shared from '../../../styles/shared.module.css';
import styles from './EvidenceTimeline.module.css';

export interface EvidenceTimelineProps {
  items?: EvidenceTimelineItem[];
  loading?: boolean;
  emptyMessage?: string;
}

const REQUIRED_FIELDS: (keyof EvidenceTimelineItem)[] = [
  'timestamp',
  'eventType',
  'source',
  'result',
  'evidenceRef',
];

export function compareTimelineItems(a: EvidenceTimelineItem, b: EvidenceTimelineItem): number {
  if (a.timestamp < b.timestamp) return -1;
  if (a.timestamp > b.timestamp) return 1;
  return a.evidenceRef.localeCompare(b.evidenceRef);
}

export function isMonotonicTimelineOrder(items: EvidenceTimelineItem[]): boolean {
  for (let i = 1; i < items.length; i++) {
    if (compareTimelineItems(items[i - 1], items[i]) > 0) return false;
  }
  return true;
}

export function hasDuplicateTimestampAmbiguity(items: EvidenceTimelineItem[]): boolean {
  const timestampCounts = new Map<string, number>();
  for (const item of items) {
    timestampCounts.set(item.timestamp, (timestampCounts.get(item.timestamp) ?? 0) + 1);
  }
  return [...timestampCounts.values()].some((count) => count > 1);
}

function validateItem(item: EvidenceTimelineItem): string | null {
  for (const field of REQUIRED_FIELDS) {
    const value = item[field];
    if (value === undefined || value === null || value === '') {
      return ERROR_COPY.missingRequiredProp(field);
    }
  }
  if (item.status && !['success', 'warning', 'error', 'info'].includes(item.status)) {
    return ERROR_COPY.unknownEnum('event status', String(item.status));
  }
  return null;
}

export function EvidenceTimeline({ items, loading, emptyMessage }: EvidenceTimelineProps) {
  if (loading) {
    return (
      <div className={styles.timeline} aria-busy="true">
        <Skeleton rows={5} variant="text" />
      </div>
    );
  }

  if (items === undefined) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('items')}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <p className={styles.empty} role="status">
        {emptyMessage ?? 'No audit events match this filter.'}
      </p>
    );
  }

  if (!isMonotonicTimelineOrder(items)) {
    return (
      <ErrorBanner
        variant="error"
        message="Evidence timeline order is not reconstructable."
        detail="Events must be supplied in monotonic timestamp order."
      />
    );
  }

  if (hasDuplicateTimestampAmbiguity(items)) {
    return (
      <ErrorBanner
        variant="error"
        message="Evidence timeline contains ambiguous duplicate timestamps."
      />
    );
  }

  return (
    <ol className={styles.timeline} aria-label="Evidence timeline">
      {items.map((item, index) => {
        const error = validateItem(item);
        if (error) {
          return (
            <li key={index} className={styles.itemError}>
              <div role="alert">{error}</div>
            </li>
          );
        }

        return (
          <li key={`${item.evidenceRef}-${index}`} className={styles.item}>
            <div className={styles.marker} aria-hidden="true" />
            <div className={styles.content}>
              <time className={styles.timestamp}>{item.timestamp}</time>
              <p className={styles.eventType}>{item.eventType}</p>
              <p className={styles.meta}>
                Source: {item.source} · Result: {item.result}
              </p>
              <div className={styles.refRow}>
                <code className={styles.ref}>{item.evidenceRef}</code>
                <CopyEvidenceRefButton evidenceRef={item.evidenceRef} />
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function CopyEvidenceRefButton({ evidenceRef }: { evidenceRef: string }) {
  const copy = async () => {
    await navigator.clipboard.writeText(evidenceRef);
  };

  return (
    <button
      type="button"
      className={[styles.copyButton, shared.focusVisible].join(' ')}
      aria-label={`Copy evidence reference ${evidenceRef}`}
      onClick={() => void copy()}
    >
      <IconCopy aria-hidden="true" />
      <span>Copy</span>
    </button>
  );
}

/** Canonical eight-step sequence for fixture testing */
export { CANONICAL_EVIDENCE_SEQUENCE } from './canonicalEvidenceSequence';

/** Deterministic ordering check for harness */
export function assertDeterministicOrder(items: EvidenceTimelineItem[]): boolean {
  return isMonotonicTimelineOrder(items);
}
