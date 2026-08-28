import type { ClaimEventRow } from '../../../detail/types';
import { CLAIM_DETAIL_COPY } from '../../../claims/claimDetailCopy';
import {
  claimEventMatchLabel,
  formatClaimEventDate,
  formatClaimEventLabel,
  formatMoneyMinorDisplay,
} from '../../../claims/claimDetailDisplay';
import { IconChevronRight } from '../../icons/StatusIcons';
import styles from './ClaimDetailPage.module.css';

export interface ClaimDetailEventsPanelProps {
  events: ClaimEventRow[];
  currencyCode: string;
}

export function ClaimDetailEventsPanel({ events, currencyCode }: ClaimDetailEventsPanelProps) {
  return (
    <section
      className={[styles.cardSection, styles.sectionEnter].join(' ')}
      style={{ animationDelay: '300ms' }}
      aria-label={CLAIM_DETAIL_COPY.events.heading}
      data-claim-events-section
    >
      <header className={styles.cardHeader}>
        <h2 className={styles.cardTitle}>{CLAIM_DETAIL_COPY.events.heading}</h2>
      </header>
      {events.length === 0 ? (
        <p className={styles.emptyCopy} role="status">
          {CLAIM_DETAIL_COPY.events.empty}
        </p>
      ) : (
        <ul className={styles.eventList} aria-label={CLAIM_DETAIL_COPY.events.heading}>
          {events.map((event) => {
            const confirmed = event.matchStatus === 'matched';
            return (
              <li
                key={event.id}
                className={confirmed ? styles.eventItemConfirmed : styles.eventItemMissing}
                data-claim-event-row
                data-claim-event-match={event.matchStatus}
              >
                <IconChevronRight
                  className={confirmed ? styles.eventMarkerOk : styles.eventMarkerMiss}
                  aria-hidden="true"
                />
                <div className={styles.eventMain}>
                  <span className={styles.eventLabel}>{formatClaimEventLabel(event.label)}</span>
                  <span className={styles.eventMeta}>
                    {formatClaimEventDate(event.occurredAt)} ·{' '}
                    {formatMoneyMinorDisplay(event.claimedMinor, currencyCode)}
                  </span>
                </div>
                <span
                  className={confirmed ? styles.matchMatched : styles.matchUnmatched}
                  data-claim-event-status
                >
                  {claimEventMatchLabel(event.matchStatus)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
