import { Link } from 'react-router-dom';
import { buildClaimTrustDrawerHref, resolveClaimIdFromEnvelopeId } from '../../../trustIndex/envelopeClaimRouting';
import { TRUST_ENVELOPE_INDEX_COPY } from '../../../trustIndex/copy';
import { IconDownload, IconFilePlus } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './TrustEnvelopeIndexPage.module.css';

export interface TrustEnvelopeIndexPageHeaderActionsProps {
  latestEnvelopeId?: string | null;
  loading?: boolean;
  readOnly?: boolean;
}

export function TrustEnvelopeIndexPageHeaderActions({
  latestEnvelopeId,
  readOnly = false,
}: TrustEnvelopeIndexPageHeaderActionsProps) {
  const hasLatest = Boolean(latestEnvelopeId);
  const exportDisabled = true;
  const exportDisabledReason = readOnly
    ? TRUST_ENVELOPE_INDEX_COPY.exportDisabledKillSwitch
    : TRUST_ENVELOPE_INDEX_COPY.exportSelectedDisabledNoSelection;

  return (
    <div className={styles.headerActions} data-trust-index-header-actions>
      {hasLatest && !readOnly && latestEnvelopeId && resolveClaimIdFromEnvelopeId(latestEnvelopeId) ? (
        <Link
          to={buildClaimTrustDrawerHref(latestEnvelopeId)}
          className={[styles.primaryAction, shared.focusVisible].join(' ')}
          data-trust-index-open-latest
        >
          <IconFilePlus className={styles.actionIcon} aria-hidden />
          {TRUST_ENVELOPE_INDEX_COPY.openLatest}
        </Link>
      ) : (
        <button
          type="button"
          className={styles.primaryAction}
          disabled
          data-trust-index-open-latest
          title={
            readOnly
              ? TRUST_ENVELOPE_INDEX_COPY.killSwitchBanner
              : TRUST_ENVELOPE_INDEX_COPY.openLatestDisabled
          }
        >
          <IconFilePlus className={styles.actionIcon} aria-hidden />
          {TRUST_ENVELOPE_INDEX_COPY.openLatest}
        </button>
      )}
      <button
        type="button"
        className={[styles.secondaryAction, shared.focusVisible].join(' ')}
        disabled={exportDisabled}
        data-trust-index-export-selected
        aria-disabled={exportDisabled}
        title={exportDisabled ? exportDisabledReason : undefined}
      >
        <IconDownload className={styles.actionIcon} aria-hidden />
        {TRUST_ENVELOPE_INDEX_COPY.exportSelected}
      </button>
    </div>
  );
}
