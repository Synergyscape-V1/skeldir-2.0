import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export interface VaultLogReadabilityViolation {
  file: string;
  rule: string;
  detail: string;
}

/**
 * Chain-of-custody readability: Vault log must not DOM-truncate forensic fields without full titles
 * and must expose a visible deep link to the audit entry.
 */
export function scanVaultLogReadability(sourceOverride?: {
  stripTsx?: string;
  displayTs?: string;
}): VaultLogReadabilityViolation[] {
  const violations: VaultLogReadabilityViolation[] = [];
  const stripTsx =
    sourceOverride?.stripTsx ??
    read('src/components/commandCenter/CommandCenterPage/AuditActivityStrip.tsx');
  const displayTs = sourceOverride?.displayTs ?? read('src/commandCenter/auditActivityDisplay.ts');

  if (/truncateTargetRef\(/.test(stripTsx)) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'dom-truncated-target',
      detail: 'Target must render full targetRef; CSS ellipsis + title handle overflow',
    });
  }

  if (!/title=\{formatAuditActorTitle\(row\)\}/.test(stripTsx)) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'missing-actor-title',
      detail: 'Actor cell must expose full actor title for hover/focus chain-of-custody',
    });
  }

  if (!/title=\{actionLabel\}/.test(stripTsx)) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'missing-action-title',
      detail: 'Action cell must expose full action label in title',
    });
  }

  if (!/title=\{row\.targetRef\}/.test(stripTsx)) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'missing-target-title',
      detail: 'Target cell must expose full targetRef in title',
    });
  }

  if (!stripTsx.includes('data-audit-entry-open')) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'missing-visible-open-link',
      detail: 'Each vault log row must expose a visible Open link to the audit entry',
    });
  }

  if (!stripTsx.includes('auditTargetCell') || !stripTsx.includes('data-audit-target-cell')) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'open-link-not-in-target-cell',
      detail: 'Open must sit in the target cell flex row — not a clipped dedicated column',
    });
  }

  if (/auditActivityColOpen/.test(stripTsx)) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'starved-open-column',
      detail: 'Dedicated Open column clips under table-layout:fixed — fold into target cell',
    });
  }

  if (stripTsx.includes('auditActivityRowLinkSr') && !stripTsx.includes('auditEntryOpenLink')) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'open-link-sr-only',
      detail: 'Open affordance must be visible — sr-only-only link is insufficient',
    });
  }

  if (/title=\{row\.actorClientId\}/.test(stripTsx)) {
    violations.push({
      file: 'AuditActivityStrip.tsx',
      rule: 'actor-title-is-client-id-only',
      detail: 'Actor title must lead with readable actorDisplay, not client id alone',
    });
  }

  if (!displayTs.includes('formatAuditActorTitle')) {
    violations.push({
      file: 'auditActivityDisplay.ts',
      rule: 'missing-actor-title-helper',
      detail: 'formatAuditActorTitle must format email/name · client id for hover',
    });
  }

  return violations;
}

export function vaultLogReadabilitySabotageFixture(): {
  stripTsx: string;
  displayTs: string;
} {
  return {
    stripTsx: `
      <td data-audit-actor-label title={row.actorClientId}>
        <span>{formatAuditActorLabel(row)}</span>
      </td>
      <td data-audit-action-label>
        <span>{formatForensicActionLabel(row.eventType)}</span>
      </td>
      <td data-audit-target>
        <span>{truncateTargetRef(row.targetRef)}</span>
      </td>
      <col className={styles.auditActivityColOpen} />
      <td data-audit-open-cell>
        <Link className={styles.auditActivityRowLinkSr}>Open</Link>
      </td>
    `,
    displayTs: `export function formatAuditActorLabel() { return ''; }`,
  };
}
