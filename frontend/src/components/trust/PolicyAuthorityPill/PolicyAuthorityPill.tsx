import { IconShield } from '../../icons/StatusIcons';
import { ERROR_COPY } from '../../../lib/copy';
import type { PolicyAuthorityState, TenantPolicyMode } from '../../../lib/types';
import { POLICY_AUTHORITY_STATES } from '../../../lib/types';
import {
  POLICY_AUTHORITY_TABLE_LABELS,
  POLICY_AUTHORITY_UI_LABELS,
} from '../../../lib/policyAuthorityLabels';
import { trustChipClassNames, type TrustChipTone } from '../TrustChip/TrustChip';
import statusText from '../../../styles/trustStatusText.module.css';
import shared from '../../../styles/shared.module.css';
import styles from './PolicyAuthorityPill.module.css';

export interface PolicyAuthorityPillProps {
  state?: PolicyAuthorityState | string;
  tenantPolicyMode?: TenantPolicyMode;
  tooltip?: string;
  loading?: boolean;
  disabled?: boolean;
  disabledReason?: string;
  showIcon?: boolean;
  shape?: 'default' | 'pill';
  size?: 'default' | 'table';
  appearance?: 'chip' | 'text';
}

const STATE_LABELS = POLICY_AUTHORITY_UI_LABELS;
const TABLE_STATE_LABELS = POLICY_AUTHORITY_TABLE_LABELS;
const TABLE_STATE_TEXT_LABELS = POLICY_AUTHORITY_TABLE_LABELS;

const POLICY_TONE: Record<PolicyAuthorityState, TrustChipTone> = {
  blocked: 'error',
  simulation_only: 'info',
  proposal_required: 'warning',
  approval_required: 'warning',
  auto_executable_within_policy: 'success',
};

const POLICY_TEXT_CLASS: Record<PolicyAuthorityState, string> = {
  blocked: statusText.labelError,
  simulation_only: statusText.labelInfo,
  proposal_required: statusText.labelWarning,
  approval_required: statusText.labelWarning,
  auto_executable_within_policy: statusText.labelSuccess,
};

export function PolicyAuthorityPill({
  state,
  tenantPolicyMode = 'design_partner',
  tooltip,
  loading,
  disabled,
  disabledReason,
  showIcon = false,
  shape = 'default',
  size = 'table',
  appearance = 'chip',
}: PolicyAuthorityPillProps) {
  if (loading) {
    return (
      <span className={styles.skeleton} aria-busy="true" aria-label="Loading policy authority">
        Simulation only
      </span>
    );
  }

  if (state === undefined || state === null || state === '') {
    return (
      <span className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('policy authority')}
      </span>
    );
  }

  if (!POLICY_AUTHORITY_STATES.includes(state as PolicyAuthorityState)) {
    return (
      <span className={[styles.pill, styles.error, shape === 'pill' ? styles.pillShape : ''].filter(Boolean).join(' ')} role="alert">
        <span className={shared.iconWithLabel}>
          {showIcon ? <IconShield aria-hidden="true" /> : null}
          <span>{ERROR_COPY.invalidAuthorityState}</span>
        </span>
      </span>
    );
  }

  const resolved = state as PolicyAuthorityState;

  if (
    resolved === 'auto_executable_within_policy' &&
    tenantPolicyMode === 'design_partner'
  ) {
    return (
      <span className={[styles.pill, styles.error, shape === 'pill' ? styles.pillShape : ''].filter(Boolean).join(' ')} role="alert">
        <span className={shared.iconWithLabel}>
          {showIcon ? <IconShield aria-hidden="true" /> : null}
          <span>{ERROR_COPY.invalidPolicyState}</span>
        </span>
      </span>
    );
  }

  if (disabled && !disabledReason) {
    return (
      <span className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('disabledReason')}
      </span>
    );
  }

  const pillClass = [
    styles.pill,
    styles[resolved],
    shape === 'pill' ? styles.pillShape : '',
    disabled ? styles.disabled : '',
  ]
    .filter(Boolean)
    .join(' ');
  const label =
    size === 'table' && appearance === 'text'
      ? TABLE_STATE_TEXT_LABELS[resolved]
      : size === 'table'
        ? TABLE_STATE_LABELS[resolved]
        : STATE_LABELS[resolved];

  if (size === 'table') {
    if (appearance === 'text') {
      return (
        <span
          className={POLICY_TEXT_CLASS[resolved]}
          data-status-text
          title={tooltip ?? STATE_LABELS[resolved]}
          role="status"
          aria-disabled={disabled ? true : undefined}
        >
          {label}
          {disabled && disabledReason ? <span className={styles.reason}>{disabledReason}</span> : null}
        </span>
      );
    }

    return (
      <span
        className={trustChipClassNames(POLICY_TONE[resolved])}
        data-trust-chip
        title={tooltip ?? STATE_LABELS[resolved]}
        role="status"
        aria-disabled={disabled ? true : undefined}
      >
        {label}
        {disabled && disabledReason ? <span className={styles.reason}>{disabledReason}</span> : null}
      </span>
    );
  }

  return (
    <span
      className={pillClass}
      title={tooltip}
      role="status"
      aria-disabled={disabled ? true : undefined}
    >
      <span className={shared.iconWithLabel}>
        {showIcon ? <IconShield aria-hidden="true" /> : null}
        <span className={styles.label}>{label}</span>
      </span>
      {disabled && disabledReason ? <span className={styles.reason}>{disabledReason}</span> : null}
    </span>
  );
}

/** Wrapper ensuring action regions expose policy pill before controls */
export interface ActionRegionProps {
  policyState: PolicyAuthorityState | string;
  tenantPolicyMode?: TenantPolicyMode;
  actionLabel: string;
  onAction?: () => void;
  actionDisabled?: boolean;
  disabledReason?: string;
}

export function ActionRegionWithPolicy({
  policyState,
  tenantPolicyMode,
  actionLabel,
  onAction,
  actionDisabled,
  disabledReason,
}: ActionRegionProps) {
  const blocked =
    policyState === 'blocked' ||
    actionDisabled ||
    policyState === 'simulation_only';

  return (
    <div className={styles.actionRegion}>
      <PolicyAuthorityPill
        state={policyState}
        tenantPolicyMode={tenantPolicyMode}
        disabled={blocked}
        disabledReason={disabledReason ?? (policyState === 'blocked' ? 'Action authority blocked' : undefined)}
      />
      <button
        type="button"
        className={[styles.actionButton, shared.focusVisible].join(' ')}
        disabled={blocked}
        onClick={onAction}
      >
        {actionLabel}
      </button>
    </div>
  );
}
