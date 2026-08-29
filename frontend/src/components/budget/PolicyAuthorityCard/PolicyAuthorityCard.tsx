import { IconWarning } from '../../icons/StatusIcons';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';
import { POLICY_AUTHORITY_EXPLANATION } from '../../../lib/policyAuthorityLabels';
import type { PolicyAuthorityState } from '../../../lib/types';
import shared from '../../../styles/shared.module.css';
import styles from './PolicyAuthorityCard.module.css';

export interface PolicyAuthorityCardProps {
  policyAuthority: PolicyAuthorityState;
}

function bodyCopy(state: PolicyAuthorityState): string {
  if (state === 'approval_required') {
    return POLICY_AUTHORITY_EXPLANATION.approvalRequired;
  }
  if (state === 'proposal_required') {
    return BUDGET_SIMULATION_COPY.policyAuthority.proposalRequiredBody;
  }
  if (state === 'blocked') {
    return BUDGET_SIMULATION_COPY.policyAuthority.blockedBody;
  }
  return BUDGET_SIMULATION_COPY.policyAuthority.simulationOnlyBody;
}

export function PolicyAuthorityCard({ policyAuthority }: PolicyAuthorityCardProps) {
  return (
    <section className={styles.panel} aria-label={BUDGET_SIMULATION_COPY.policyAuthority.title} data-policy-authority-card data-budget-elevated-panel="true">
      <div className={styles.headerRow}>
        <h3 className={styles.title}>{BUDGET_SIMULATION_COPY.policyAuthority.title}</h3>
        <span className={shared.iconWithLabel}>
          <IconWarning aria-hidden="true" />
          <PolicyAuthorityPill state={policyAuthority} />
        </span>
      </div>
      <p className={styles.body}>{bodyCopy(policyAuthority)}</p>
    </section>
  );
}
