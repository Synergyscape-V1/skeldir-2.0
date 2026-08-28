import { Link, useLocation } from 'react-router-dom';
import type { TrustEnvelopeSubjectData } from '../../../detail/types';
import { TRUST_ENVELOPE_DETAIL_COPY } from '../../../trustIndex/trustEnvelopeDetailCopy';
import { IconExternalLink } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import panelStyles from './TrustEnvelopeDetailPanel.module.css';
import styles from './TrustEnvelopeDetailSubjectPanel.module.css';

export interface TrustEnvelopeDetailSubjectPanelProps {
  subject: TrustEnvelopeSubjectData;
}

export function TrustEnvelopeDetailSubjectPanel({ subject }: TrustEnvelopeDetailSubjectPanelProps) {
  const location = useLocation();
  const parentState = { parentSearch: location.search };
  const copy = TRUST_ENVELOPE_DETAIL_COPY.panels.subject;

  return (
    <section className={panelStyles.panel} data-panel="subject" data-trust-envelope-subject-panel>
      <h2 className={panelStyles.panelTitle}>{copy.title}</h2>
      <dl className={styles.fieldGrid}>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.subjectType}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-subject-type>
            {subject.subjectType}
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.subjectIdentifier}</dt>
          <dd className={styles.fieldValueMono} data-trust-envelope-subject-identifier>
            {subject.subjectIdentifier}
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.relatedClaimId}</dt>
          <dd className={styles.fieldValue}>
            <Link
              to={subject.relatedClaimHref}
              state={parentState}
              className={[styles.fieldLink, shared.focusVisible].join(' ')}
              data-trust-envelope-related-claim
              aria-label={copy.openRelatedClaim(subject.relatedClaimId)}
            >
              {subject.relatedClaimId}
            </Link>
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.relatedChannel}</dt>
          <dd className={styles.fieldValue}>
            <Link
              to={subject.relatedChannelHref}
              state={parentState}
              className={[styles.fieldLink, styles.fieldLinkWithIcon, shared.focusVisible].join(' ')}
              data-trust-envelope-related-channel
              aria-label={copy.openRelatedChannel(subject.relatedChannelLabel)}
            >
              {subject.relatedChannelLabel}
              <IconExternalLink className={styles.externalIcon} aria-hidden />
            </Link>
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.sourceSystem}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-source-system>
            {subject.sourceSystem}
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.timeWindow}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-time-window>
            {subject.timeWindowLabel}
          </dd>
        </div>
      </dl>
    </section>
  );
}
