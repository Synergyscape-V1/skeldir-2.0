import { Link, useNavigate } from 'react-router-dom';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import { useAuditActivityStrip } from '../../../commandCenter/useAuditActivityStrip';
import type { CommandCenterAggregate } from '../../../commandCenter/types';
import {
  buildAuditLedgerDeepLink,
  formatAuditActorLabel,
  formatAuditActorTitle,
  formatForensicTimestampUtc,
} from '../../../commandCenter/auditActivityDisplay';
import { formatForensicActionLabel } from '../../../operationalAudit/forensicAuditDisplay';
import { IconArrowUpRight } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './CommandCenterSubcomponents.module.css';

export function AuditActivityStrip({ aggregate }: { aggregate: CommandCenterAggregate }) {
  const rows = useAuditActivityStrip(aggregate.auditActivity);
  const navigate = useNavigate();

  return (
    <section
      data-audit-activity-strip
      data-audit-refresh-model="poll-60s"
      className={[styles.tableCard, styles.auditActivityCard, styles.section].join(' ')}
    >
      <header className={styles.auditActivityHeader}>
        <h2 className={styles.sectionTitle}>{COMMAND_CENTER_COPY.auditActivity}</h2>
        <Link
          to="/app/audit?log=forensic_log"
          className={[styles.auditLedgerLink, shared.focusVisible].join(' ')}
          data-view-audit-ledger
        >
          {COMMAND_CENTER_COPY.viewAuditLedger}
          <IconArrowUpRight className={styles.summaryDrillDownChevron} />
        </Link>
      </header>

      {rows.length === 0 ? (
        <p className={styles.emptyState}>{COMMAND_CENTER_COPY.auditStripEmpty}</p>
      ) : (
        <div className={styles.auditActivityTableWrap}>
          <table className={styles.auditActivityTable}>
            <caption className={styles.auditActivityCaption}>{COMMAND_CENTER_COPY.auditStripCaption}</caption>
            <colgroup>
              <col className={styles.auditActivityColTimestamp} />
              <col className={styles.auditActivityColActor} />
              <col className={styles.auditActivityColAction} />
              <col className={styles.auditActivityColTarget} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{COMMAND_CENTER_COPY.auditStripColumns.timestamp}</th>
                <th scope="col">{COMMAND_CENTER_COPY.auditStripColumns.actor}</th>
                <th scope="col">{COMMAND_CENTER_COPY.auditStripColumns.action}</th>
                <th scope="col">{COMMAND_CENTER_COPY.auditStripColumns.target}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const href = buildAuditLedgerDeepLink(row);
                const actorLabel = formatAuditActorLabel(row);
                const actionLabel = formatForensicActionLabel(row.eventType);
                return (
                  <tr
                    key={row.eventId}
                    data-audit-activity-row={row.eventId}
                    className={styles.auditActivityRow}
                    tabIndex={0}
                    role="link"
                    aria-label={COMMAND_CENTER_COPY.openAuditEntryAria(actionLabel, row.targetRef)}
                    onClick={() => navigate(href)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        navigate(href);
                      }
                    }}
                  >
                    <td data-audit-timestamp title={formatForensicTimestampUtc(row.occurredAt)}>
                      <time className={styles.auditTimestamp} dateTime={row.occurredAt}>
                        {formatForensicTimestampUtc(row.occurredAt)}
                      </time>
                    </td>
                    <td data-audit-actor-label title={formatAuditActorTitle(row)}>
                      <span className={styles.auditActorLabel} data-audit-actor-full={actorLabel}>
                        {actorLabel}
                      </span>
                    </td>
                    <td data-audit-action-label title={actionLabel}>
                      <span className={styles.auditActionLabel} data-audit-action-full={actionLabel}>
                        {actionLabel}
                      </span>
                    </td>
                    <td data-audit-target title={row.targetRef}>
                      <div className={styles.auditTargetCell} data-audit-target-cell>
                        <span className={styles.auditTargetRef} data-audit-target-full={row.targetRef}>
                          {row.targetRef}
                        </span>
                        <Link
                          to={href}
                          className={[styles.auditEntryOpenLink, shared.focusVisible].join(' ')}
                          data-audit-entry-open={row.eventId}
                          data-audit-chip={row.eventId}
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => event.stopPropagation()}
                          aria-label={COMMAND_CENTER_COPY.openAuditEntryAria(actionLabel, row.targetRef)}
                        >
                          {COMMAND_CENTER_COPY.openAuditEntry}
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
