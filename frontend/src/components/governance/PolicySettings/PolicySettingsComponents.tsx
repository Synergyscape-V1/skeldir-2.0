import type { ReactNode } from 'react';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import type { PolicyAuthorityState } from '../../../lib/types';
import { GOVERNANCE_COPY } from '../../../governance/copy';
import type { PolicyActionCategory, PolicyCategoryConfig } from '../../../governance/types';
import shared from '../../../styles/shared.module.css';
import styles from './PolicySettingsComponents.module.css';

export interface PolicyAuthorityRowProps {
  config: PolicyCategoryConfig;
  canConfigure?: boolean;
  onConfigure?: (category: PolicyActionCategory) => void;
}

export function PolicyAuthorityRow({ config, canConfigure, onConfigure }: PolicyAuthorityRowProps) {
  return (
    <div className={styles.row} data-policy-category={config.category}>
      <div className={styles.label}>
        {GOVERNANCE_COPY.policyCategoryLabels[config.category]}
      </div>
      <PolicyAuthorityPill
        state={config.authority}
        tenantPolicyMode="design_partner"
      />
      {config.autoExecuteConstraints ? (
        <div className={styles.constraints} role="group" aria-label="Auto-execute constraints">
          <span>Ceiling: {config.autoExecuteConstraints.budgetCeilingMinor}</span>
          <span>Cooldown: {config.autoExecuteConstraints.cooldownPeriodHours}h</span>
          <span>Hysteresis: {config.autoExecuteConstraints.hysteresisThresholdPercent}%</span>
        </div>
      ) : null}
      <button
        type="button"
        className={[styles.configure, shared.focusVisible].join(' ')}
        disabled={!canConfigure}
        onClick={() => onConfigure?.(config.category)}
      >
        {GOVERNANCE_COPY.policyConfigureButton}
      </button>
    </div>
  );
}

export function PolicyInvalidAuthorityBanner() {
  return (
    <div className={styles.invalidBanner} role="alert" data-policy-invalid-banner>
      Invalid authority state returned.
    </div>
  );
}

export interface PolicyStatusOverviewProps {
  modeLabel: string;
  children?: ReactNode;
}

export function PolicyStatusOverview({ modeLabel, children }: PolicyStatusOverviewProps) {
  return (
    <section className={styles.overview} aria-labelledby="policy-overview-heading">
      <h3 id="policy-overview-heading">Policy status</h3>
      <p>
        <span className={styles.modeLabel}>{GOVERNANCE_COPY.policyModeLabel}:</span> {modeLabel}
      </p>
      {children}
    </section>
  );
}

export interface PolicyActionCategoryListProps {
  categories: PolicyCategoryConfig[];
  canConfigure?: boolean;
  onConfigure?: (category: PolicyActionCategory) => void;
}

export function PolicyActionCategoryList({
  categories,
  canConfigure,
  onConfigure,
}: PolicyActionCategoryListProps) {
  return (
    <div className={styles.list} role="list" aria-label="Policy action categories">
      {categories.map((config) => (
        <PolicyAuthorityRow
          key={config.category}
          config={config}
          canConfigure={canConfigure}
          onConfigure={onConfigure}
        />
      ))}
    </div>
  );
}

export interface PolicyAuthoritySelectorProps {
  value: PolicyAuthorityState;
  onChange: (value: PolicyAuthorityState) => void;
  disabled?: boolean;
}

const SELECTABLE_STATES: PolicyAuthorityState[] = [
  'blocked',
  'simulation_only',
  'proposal_required',
  'approval_required',
  'auto_executable_within_policy',
];

export function PolicyAuthoritySelector({
  value,
  onChange,
  disabled,
}: PolicyAuthoritySelectorProps) {
  return (
    <fieldset className={styles.selector} disabled={disabled}>
      <legend>Policy authority</legend>
      {SELECTABLE_STATES.map((state) => (
        <label key={state} className={styles.radioLabel}>
          <input
            type="radio"
            name="policy-authority"
            value={state}
            checked={value === state}
            onChange={() => onChange(state)}
            className={shared.focusVisible}
          />
          <PolicyAuthorityPill state={state} tenantPolicyMode="full" />
        </label>
      ))}
    </fieldset>
  );
}

export interface PolicyConstraintFieldsProps {
  budgetCeiling: string;
  cooldownHours: string;
  hysteresisPercent: string;
  onBudgetCeilingChange: (v: string) => void;
  onCooldownChange: (v: string) => void;
  onHysteresisChange: (v: string) => void;
  disabled?: boolean;
}

export function PolicyConstraintFields({
  budgetCeiling,
  cooldownHours,
  hysteresisPercent,
  onBudgetCeilingChange,
  onCooldownChange,
  onHysteresisChange,
  disabled,
}: PolicyConstraintFieldsProps) {
  return (
    <div className={styles.constraintsForm} role="group" aria-label="Auto-execute constraints">
      <label>
        {GOVERNANCE_COPY.autoExecuteBudgetCeiling}
        <input
          type="number"
          value={budgetCeiling}
          disabled={disabled}
          onChange={(e) => onBudgetCeilingChange(e.target.value)}
          className={shared.focusVisible}
          min={0}
        />
      </label>
      <label>
        {GOVERNANCE_COPY.autoExecuteCooldown}
        <input
          type="number"
          value={cooldownHours}
          disabled={disabled}
          onChange={(e) => onCooldownChange(e.target.value)}
          className={shared.focusVisible}
          min={1}
        />
      </label>
      <label>
        {GOVERNANCE_COPY.autoExecuteHysteresis}
        <input
          type="number"
          value={hysteresisPercent}
          disabled={disabled}
          onChange={(e) => onHysteresisChange(e.target.value)}
          className={shared.focusVisible}
          min={0}
          max={100}
        />
      </label>
    </div>
  );
}
