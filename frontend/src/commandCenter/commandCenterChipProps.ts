/** Compact rectangular chips for supervisory surfaces (no shield icons). */
export const COMMAND_CENTER_CHIP_PROPS = {
  showIcon: false,
  size: 'table' as const,
} as const;

/** Product-wide default for AuthorityBadge and PolicyAuthorityPill outside Level 0 specimens. */
export const PRODUCT_TABLE_CHIP_PROPS = COMMAND_CENTER_CHIP_PROPS;

export const COMMAND_CENTER_POLICY_CHIP_PROPS = {
  ...COMMAND_CENTER_CHIP_PROPS,
  tenantPolicyMode: 'full' as const,
} as const;

/** Shared compact table chips for supervisory ledgers (Command Center, Claims, Channels). */
export const SUPERVISORY_TABLE_CHIP = { table: true as const };

/** Text-only status labels for dense supervisory tables (no pill chrome). */
export const SUPERVISORY_TABLE_STATUS_TEXT = { variant: 'text' as const, table: true, compact: true };

/** Trust index table surfaces — authority, policy, benchmark, and signature chips. */
export const TRUST_INDEX_TABLE_CHIP = SUPERVISORY_TABLE_CHIP;
export const TRUST_INDEX_AUTHORITY_CHIP = COMMAND_CENTER_CHIP_PROPS;
export const TRUST_INDEX_POLICY_CHIP = COMMAND_CENTER_POLICY_CHIP_PROPS;
