import type { TrustEnvelopePolicyAuthorityData } from '../../../detail/types';
import { POLICY_AUTHORITY_STATES } from '../../../lib/types';
import { TRUST_ENVELOPE_DETAIL_COPY } from '../../../trustIndex/trustEnvelopeDetailCopy';
import { PolicyAuthorityPill } from '../PolicyAuthorityPill/PolicyAuthorityPill';
import { IconCheckmark, IconProhibited } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import panelStyles from './TrustEnvelopeDetailPanel.module.css';
import styles from './TrustEnvelopeDetailPolicyAuthorityPanel.module.css';

export interface TrustEnvelopeDetailPolicyAuthorityPanelProps {
  data: TrustEnvelopePolicyAuthorityData;
}

function validatePolicyAuthorityIntegrity(data: TrustEnvelopePolicyAuthorityData): string | null {
  if (!POLICY_AUTHORITY_STATES.includes(data.state)) {
    return 'Invalid policy authority state.';
  }
  if (!data.explanation.trim()) {
    return 'Policy authority explanation is required.';
  }
  if (data.allowedActions.length === 0 || data.blockedActions.length === 0) {
    return 'Allowed and blocked action lists are required.';
  }
  if (!data.auditRequirement.trim()) {
    return 'Audit requirement is required.';
  }
  return null;
}

export function TrustEnvelopeDetailPolicyAuthorityPanel({
  data,
}: TrustEnvelopeDetailPolicyAuthorityPanelProps) {
  const copy = TRUST_ENVELOPE_DETAIL_COPY.panels.policyAuthority;
  const integrityError = validatePolicyAuthorityIntegrity(data);

  if (integrityError) {
    return (
      <section className={panelStyles.panel} data-panel="policy" role="alert">
        <div className={shared.errorState}>{integrityError}</div>
      </section>
    );
  }

  return (
    <section
      className={panelStyles.panel}
      data-panel="policy"
      data-trust-envelope-policy-authority-panel
      data-trust-envelope-policy-state={data.state}
    >
      <div className={styles.titleRow}>
        <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
      </div>

      <div className={styles.authorityRow}>
        <PolicyAuthorityPill state={data.state} showIcon={false} />
        <p className={styles.explanation} data-trust-envelope-policy-explanation>
          <span className={styles.explanationLabel}>{copy.authorityExplanation}:</span>{' '}
          {data.explanation}
        </p>
      </div>

      <div className={styles.actionGrid}>
        <div className={styles.actionColumn}>
          <h3 className={styles.actionHeading}>
            <IconCheckmark className={styles.allowedIcon} size={16} />
            {copy.allowedActions}
          </h3>
          <ul className={styles.actionList} data-trust-envelope-allowed-actions>
            {data.allowedActions.map((action) => (
              <li key={action} className={styles.actionItem}>
                <IconCheckmark className={styles.itemAllowedIcon} size={16} />
                {action}
              </li>
            ))}
          </ul>
        </div>
        <div className={styles.actionColumn}>
          <h3 className={styles.actionHeading}>
            <IconProhibited className={styles.blockedIcon} aria-hidden />
            {copy.blockedActions}
          </h3>
          <ul className={styles.actionList} data-trust-envelope-blocked-actions>
            {data.blockedActions.map((action) => (
              <li key={action} className={styles.actionItem}>
                <IconProhibited className={styles.itemBlockedIcon} aria-hidden />
                {action}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className={styles.auditRequirement} data-trust-envelope-policy-audit-requirement>
        <span className={styles.auditLabel}>{copy.auditRequirement}:</span> {data.auditRequirement}
      </p>
    </section>
  );
}
