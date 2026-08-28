import type { ExceptionQueueRowDTO } from '../../../ledger/types';
import { EXCEPTION_CATEGORY_LABELS, EXCEPTIONS_PAGE_COPY } from '../../../exceptions/copy';
import { formatExceptionCreatedAge } from '../../../exceptions/formatExceptionAge';
import {
  COMMAND_CENTER_POLICY_CHIP_PROPS,
  SUPERVISORY_TABLE_STATUS_TEXT,
} from '../../../commandCenter/commandCenterChipProps';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { ExceptionSeverityBadge } from '../ExceptionSeverityBadge/ExceptionSeverityBadge';
import { ExceptionStatusBadge } from '../ExceptionStatusBadge/ExceptionStatusBadge';
import shared from '../../../styles/shared.module.css';
import styles from './ExceptionsTableCells.module.css';

export function ExceptionSeverityCell({ row }: { row: ExceptionQueueRowDTO }) {
  return (
    <div className={styles.chipCell} data-exception-severity-cell={row.exceptionId}>
      <ExceptionSeverityBadge severity={row.severity} {...SUPERVISORY_TABLE_STATUS_TEXT} />
    </div>
  );
}

export function ExceptionCategoryCell({ row }: { row: ExceptionQueueRowDTO }) {
  return (
    <span className={styles.truncatedMetaText} data-exception-category={row.category} title={EXCEPTION_CATEGORY_LABELS[row.category]}>
      {EXCEPTION_CATEGORY_LABELS[row.category]}
    </span>
  );
}

export function ExceptionSummaryCell({ row }: { row: ExceptionQueueRowDTO }) {
  return (
    <span className={styles.summaryText} title={row.summary} data-exception-summary={row.exceptionId}>
      {row.summary}
    </span>
  );
}

export function ExceptionAffectedObjectCell({ row }: { row: ExceptionQueueRowDTO }) {
  return (
    <span className={styles.truncatedMetaText} title={row.affectedObjectLabel} data-exception-object={row.exceptionId}>
      {row.affectedObjectLabel}
    </span>
  );
}

export function ExceptionPolicyCell({ row }: { row: ExceptionQueueRowDTO }) {
  return (
    <div className={styles.chipCell}>
      <PolicyAuthorityPill
        state={row.policyAuthority}
        {...COMMAND_CENTER_POLICY_CHIP_PROPS}
        appearance="text"
      />
    </div>
  );
}

export function ExceptionAuditEventCell({ row }: { row: ExceptionQueueRowDTO }) {
  return (
    <span className={styles.truncatedMetaText} title={row.lastAuditEvent}>
      {row.lastAuditEvent}
    </span>
  );
}

export function ExceptionCreatedAgeCell({ row }: { row: ExceptionQueueRowDTO }) {
  return (
    <span className={styles.metaText} data-exception-created-age={row.exceptionId}>
      {formatExceptionCreatedAge(row.createdAt)}
    </span>
  );
}

export function ExceptionStatusCell({ row }: { row: ExceptionQueueRowDTO }) {
  return (
    <div className={styles.chipCell}>
      <ExceptionStatusBadge status={row.status} {...SUPERVISORY_TABLE_STATUS_TEXT} />
    </div>
  );
}

export function ExceptionActionCell({
  row,
  disabled,
  onReview,
}: {
  row: ExceptionQueueRowDTO;
  disabled?: boolean;
  onReview: (row: ExceptionQueueRowDTO, trigger: HTMLButtonElement) => void;
}) {
  const label =
    row.actionKind === 'open' ? EXCEPTIONS_PAGE_COPY.table.open : EXCEPTIONS_PAGE_COPY.table.review;

  return (
    <button
      type="button"
      className={[styles.openButton, shared.focusVisible].join(' ')}
      disabled={disabled}
      data-exception-action={row.exceptionId}
      data-exception-detail-trigger
      aria-label={`${label} ${row.summary}`}
      onClick={(event) => {
        event.stopPropagation();
        onReview(row, event.currentTarget);
      }}
    >
      {label}
    </button>
  );
}
