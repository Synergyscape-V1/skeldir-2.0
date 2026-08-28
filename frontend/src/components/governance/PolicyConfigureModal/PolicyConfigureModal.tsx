import { useState } from 'react';
import { Modal } from '../../layout/Modal/Modal';
import type { PolicyAuthorityState } from '../../../lib/types';
import { GOVERNANCE_COPY } from '../../../governance/copy';
import type { PolicyActionCategory, PolicyCategoryConfig } from '../../../governance/types';
import {
  PolicyAuthoritySelector,
  PolicyConstraintFields,
  PolicyInvalidAuthorityBanner,
} from '../PolicySettings/PolicySettingsComponents';
import shared from '../../../styles/shared.module.css';
import styles from './PolicyConfigureModal.module.css';

export interface PolicyConfigureModalProps {
  open: boolean;
  category?: PolicyActionCategory;
  initialConfig?: PolicyCategoryConfig;
  tenantMode: 'design_partner' | 'full';
  savePending?: boolean;
  saveError?: string;
  onClose: () => void;
  onSave: (
    category: PolicyActionCategory,
    authority: PolicyAuthorityState,
    constraints?: {
      budgetCeilingMinor: number;
      cooldownPeriodHours: number;
      hysteresisThresholdPercent: number;
    },
  ) => Promise<{ ok: boolean; error?: string }>;
}

export function PolicyConfigureModal({
  open,
  category,
  initialConfig,
  tenantMode,
  savePending,
  saveError,
  onClose,
  onSave,
}: PolicyConfigureModalProps) {
  const [authority, setAuthority] = useState<PolicyAuthorityState>(
    initialConfig?.authority ?? 'blocked',
  );
  const [budgetCeiling, setBudgetCeiling] = useState(
    String(initialConfig?.autoExecuteConstraints?.budgetCeilingMinor ?? ''),
  );
  const [cooldown, setCooldown] = useState(
    String(initialConfig?.autoExecuteConstraints?.cooldownPeriodHours ?? ''),
  );
  const [hysteresis, setHysteresis] = useState(
    String(initialConfig?.autoExecuteConstraints?.hysteresisThresholdPercent ?? ''),
  );

  const showInvalid =
    authority === 'auto_executable_within_policy' && tenantMode === 'design_partner';

  const showConstraints = authority === 'auto_executable_within_policy' && !showInvalid;

  const handleSave = async () => {
    if (!category) return;
    if (showInvalid) return;
    const constraints = showConstraints
      ? {
          budgetCeilingMinor: parseInt(budgetCeiling, 10) || 0,
          cooldownPeriodHours: parseInt(cooldown, 10) || 0,
          hysteresisThresholdPercent: parseInt(hysteresis, 10) || 0,
        }
      : undefined;
    await onSave(category, authority, constraints);
  };

  const title = category
    ? `Configure ${GOVERNANCE_COPY.policyCategoryLabels[category]}`
    : 'Configure policy';

  return (
    <Modal open={open} onClose={onClose} title={title}>
      {showInvalid ? <PolicyInvalidAuthorityBanner /> : null}
      <PolicyAuthoritySelector
        value={authority}
        onChange={setAuthority}
        disabled={savePending}
      />
      {showConstraints ? (
        <PolicyConstraintFields
          budgetCeiling={budgetCeiling}
          cooldownHours={cooldown}
          hysteresisPercent={hysteresis}
          onBudgetCeilingChange={setBudgetCeiling}
          onCooldownChange={setCooldown}
          onHysteresisChange={setHysteresis}
          disabled={savePending}
        />
      ) : null}
      {saveError ? (
        <p role="alert" className={styles.error}>
          {saveError}
        </p>
      ) : null}
      <button
        type="button"
        className={[styles.save, shared.focusVisible].join(' ')}
        disabled={savePending || showInvalid}
        aria-busy={savePending}
        onClick={() => void handleSave()}
      >
        {savePending ? GOVERNANCE_COPY.policySaving : GOVERNANCE_COPY.policySaveButton}
      </button>
    </Modal>
  );
}
