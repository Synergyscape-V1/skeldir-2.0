import { useNavigate } from 'react-router-dom';
import type { KeyboardEvent, ReactNode } from 'react';
import type { RecentEnvelopeRow } from '../../../commandCenter/types';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import {
  matchVerdictLabel,
  resolveRecentEnvelopeDrillDown,
  trustSignalLabel,
} from '../../../commandCenter/recentEnvelopeDisplay';
import { COMMAND_CENTER_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { formatMoneyMinorDisplay } from '../../../lib/money';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import shared from '../../../styles/shared.module.css';
import styles from './RecentTrustEnvelopesCells.module.css';

export function RecentEnvelopeSubjectCell({ row }: { row: RecentEnvelopeRow }) {
  return (
    <span className={styles.subjectRef} title={row.subjectRef} data-recent-envelope-subject={row.envelopeId}>
      {row.subjectRef}
    </span>
  );
}

export function RecentEnvelopeVerifiedRevenueCell({ row }: { row: RecentEnvelopeRow }) {
  return (
    <span className={styles.verifiedRevenue} data-recent-envelope-verified-revenue={row.envelopeId}>
      {formatMoneyMinorDisplay(row.verifiedRevenueMinor, row.currencyCode)}
    </span>
  );
}

export function RecentEnvelopeMatchVerdictCell({ row }: { row: RecentEnvelopeRow }) {
  return (
    <span className={styles.matchVerdict} data-recent-envelope-match-verdict={row.envelopeId}>
      {matchVerdictLabel(row.matchVerdict)}
    </span>
  );
}

export function RecentEnvelopePolicyCell({ row }: { row: RecentEnvelopeRow }) {
  return (
    <div className={styles.policyCell}>
      <PolicyAuthorityPill
        state={row.policyAuthority}
        tenantPolicyMode="design_partner"
        {...COMMAND_CENTER_CHIP_PROPS}
        appearance="text"
      />
    </div>
  );
}

export function RecentEnvelopeTrustSignalCell({ row }: { row: RecentEnvelopeRow }) {
  const label = trustSignalLabel(row.trustSignal);
  if (!label) {
    return <span className={styles.trustSignalBlank} aria-hidden data-recent-envelope-trust-signal-empty />;
  }
  return (
    <span
      className={
        row.trustSignal === 'estimator_transition' ? styles.trustSignalTransition : styles.trustSignalUnavailable
      }
      data-recent-envelope-trust-signal={row.trustSignal}
      role="status"
    >
      {label}
    </span>
  );
}

export function RecentEnvelopeInteractiveRow({
  row,
  children,
}: {
  row: RecentEnvelopeRow;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  const drillDown = resolveRecentEnvelopeDrillDown(row);

  const activate = () => {
    navigate(drillDown.href, {
      state: { fromCommandCenterRecent: true, recentSubjectRef: row.subjectRef },
    });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      activate();
    }
  };

  return (
    <tr
      data-recent-envelope={row.envelopeId}
      data-recent-envelope-row-link={row.envelopeId}
      data-table-row-interactive
      data-recent-envelope-drill-focus={drillDown.focus ?? 'summary'}
      className={[styles.interactiveRow, shared.focusVisible].join(' ')}
      tabIndex={0}
      role="link"
      aria-label={`${COMMAND_CENTER_COPY.recentEnvelopeTableColumns.subjectRef}: ${row.subjectRef}`}
      onClick={activate}
      onKeyDown={onKeyDown}
    >
      {children}
    </tr>
  );
}
