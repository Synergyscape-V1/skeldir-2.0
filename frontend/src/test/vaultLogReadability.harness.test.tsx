import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  scanVaultLogReadability,
  vaultLogReadabilitySabotageFixture,
} from '../audit/vaultLogReadabilityScan';
import { COMMAND_CENTER_AUDIT_ACTIVITY } from '../commandCenter/commandCenterAuditFixtures';
import {
  buildAuditLedgerDeepLink,
  formatAuditActorLabel,
  formatAuditActorTitle,
} from '../commandCenter/auditActivityDisplay';
import {
  renderCommandCenter,
  resetLevel10HarnessState,
  seedShellAuth,
  waitForCommandCenterLoaded,
} from './level10.helpers';

beforeEach(() => {
  resetLevel10HarnessState();
});

describe('CRHAID 3 — Vault log readability remediation', () => {
  describe('Positive controls', () => {
    it('actor title leads with readable display, not client-id alone', () => {
      const row = COMMAND_CENTER_AUDIT_ACTIVITY[0]!;
      expect(formatAuditActorLabel(row)).toBe(row.actorDisplay);
      expect(formatAuditActorTitle(row)).toContain(row.actorDisplay);
      expect(formatAuditActorTitle(row)).toContain(row.actorClientId);
      expect(formatAuditActorTitle(row).startsWith(row.actorClientId)).toBe(false);
    });

    it('DOM retains full actor, action, and target with titles + visible Open link', async () => {
      seedShellAuth();
      renderCommandCenter('/app');
      await waitForCommandCenterLoaded();
      await waitFor(() => expect(document.querySelector('[data-audit-activity-row]')).toBeTruthy());

      const tr = document.querySelector('[data-audit-activity-row]') as HTMLElement;
      const actor = tr.querySelector('[data-audit-actor-label]');
      const action = tr.querySelector('[data-audit-action-label]');
      const target = tr.querySelector('[data-audit-target]');
      const open = tr.querySelector('[data-audit-entry-open]');
      const actorFull = tr.querySelector('[data-audit-actor-full]')?.getAttribute('data-audit-actor-full');
      const actionFull = tr.querySelector('[data-audit-action-full]')?.getAttribute('data-audit-action-full');
      const targetFull = tr.querySelector('[data-audit-target-full]')?.getAttribute('data-audit-target-full');

      expect(actorFull).toBeTruthy();
      expect(actionFull).toBeTruthy();
      expect(targetFull).toBeTruthy();
      expect(actor?.getAttribute('title')).toContain(actorFull!);
      expect(actor?.textContent).toBe(actorFull);
      expect(actor?.textContent).not.toMatch(/\.\.\.$/);

      expect(action?.getAttribute('title')).toBe(actionFull);
      expect(action?.textContent).toBe(actionFull);
      expect(actionFull!.length).toBeGreaterThan(8);

      expect(target?.getAttribute('title')).toBe(targetFull);
      expect(tr.querySelector('[data-audit-target-full]')?.textContent).toBe(targetFull);
      expect(tr.querySelector('[data-audit-target-full]')?.textContent).not.toMatch(/…/);

      expect(open).toBeTruthy();
      expect(open?.textContent).toMatch(/Open/i);
      expect(open?.getAttribute('href')).toMatch(/^\/app\/audit\/events\//);
      expect(open?.className).toMatch(/auditEntryOpenLink/);
      expect(open?.className).not.toMatch(/auditActivityRowLinkSr/);
      expect(tr.querySelector('[data-audit-target-cell]')?.contains(open)).toBe(true);
      expect(document.querySelector('[data-audit-open-cell]')).toBeNull();
    });

    it('Open link navigates to forensic audit entry without Overview dead-end', async () => {
      const user = userEvent.setup();
      seedShellAuth();
      const { router } = renderCommandCenter('/app');
      await waitForCommandCenterLoaded();

      const row = COMMAND_CENTER_AUDIT_ACTIVITY[0]!;
      const open = await waitFor(() => {
        const el = document.querySelector(`[data-audit-entry-open="${row.eventId}"]`);
        expect(el).toBeTruthy();
        return el as HTMLElement;
      });

      await user.click(open);
      await waitFor(() => {
        expect(router.state.location.pathname).toBe(`/app/audit/events/${row.eventId}`);
      });
    });

    it('static integrity scan passes on live sources', () => {
      expect(scanVaultLogReadability()).toEqual([]);
    });
  });

  describe('Negative controls', () => {
    it('rejects DOM truncation, missing titles, and sr-only-only Open', () => {
      const violations = scanVaultLogReadability(vaultLogReadabilitySabotageFixture());
      expect(violations.some((v) => v.rule === 'dom-truncated-target')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-action-title')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-target-title')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-visible-open-link')).toBe(true);
      expect(violations.some((v) => v.rule === 'actor-title-is-client-id-only')).toBe(true);
      expect(violations.some((v) => v.rule === 'open-link-sr-only')).toBe(true);
      expect(violations.some((v) => v.rule === 'starved-open-column')).toBe(true);
      expect(violations.some((v) => v.rule === 'missing-actor-title-helper')).toBe(true);
    });
  });

  describe('Meta-negative control', () => {
    it('harness is non-vacuous: sabotage fails while live passes', () => {
      expect(scanVaultLogReadability()).toEqual([]);
      expect(scanVaultLogReadability(vaultLogReadabilitySabotageFixture()).length).toBeGreaterThan(0);
    });
  });
});
