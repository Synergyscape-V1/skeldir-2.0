import { screen, waitFor, within, render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  assertLevel9FlowsExist,
  runLevel9ClientProbe,
  runLevel9NegativeScopeScan,
  runLevel9SabotageProbes,
  runLevel9SourceIntegrityProbes,
  runLevel9SourceSabotageProbes,
} from '../audit/level9NegativeScopeScan';
import { runLevel8NegativeScopeScan } from '../audit/level8NegativeScopeScan';
import { runPrivacyScan } from '../audit/privacyScan';
import { runSecretScan } from '../audit/secretScan';
import * as claimExportModule from '../actions/claimExportClient';
import {
  exportVerifiedReport,
  resetClaimExportTestMode,
  setClaimExportDelayForTests,
  setClaimExportTestMode,
} from '../actions/claimExportClient';
import {
  resetTrustActionTestMode,
  setTrustActionTestMode,
  exportArtifact,
} from '../actions/trustEnvelopeActionClient';
import { exportAuditReconstruction, resetAuditExportTestMode, setAuditExportTestMode } from '../actions/auditExportClient';
import {
  resetBudgetProposalTestMode,
  setBudgetProposalTestMode,
  submitBudgetProposal,
} from '../actions/budgetProposalClient';
import {
  acknowledgeException,
  createProposal,
  markDisputed,
  requestMoreEvidence,
  resetExceptionActionTestMode,
  setExceptionActionTestMode,
  suppressSimilarAlerts,
} from '../actions/exceptionActionClient';
import { buildCanonicalTrustEnvelopeJson, generateIdempotencyKey, resetIdempotencyStoreForTests, simulateHardRefreshForTests } from '../actions/idempotency';
import { buildMinimalTrustEnvelopeJsonContract } from '../trustIndex/trustEnvelopeJsonContract';
import { resetSubsystemSafetyForTests, setSubsystemBlockForTests, setSubsystemHealthForTests } from '../actions/systemSafety';
import {
  resetClaimDetailTestMode,
  setClaimDetailPolicyAuthorityForTests,
} from '../claims/claimDetailClient';
import { resetDefaultTrustEnvelopeDetailClient } from '../trustIndex/trustEnvelopeDetailClient';
import { resetDefaultBudgetSimulationDetailClient, setBudgetDetailPolicyAuthorityForTests } from '../budget/budgetSimulationDetailClient';
import { resetDefaultExceptionDetailClient } from '../exceptions/exceptionDetailClient';
import { establishTenant, setBootstrapReady } from '../auth/sessionStore';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { setCurrentUserRole } from '../governance/governanceStore';
import { MAX_COPY_JSON_BYTES, MAX_EXPORT_PREVIEW_BYTES } from '../actions/bounds';
import {
  assertNoFalseSuccessIdentifiers,
  assertPreviewDomBounded,
  confirmGovernedAction,
  createDetailShellRouter,
  createClaimExportNavRouter,
  EXCEPTIONS_HARNESS_PATH,
  executeAuditExportSuccess,
  executeBudgetProposalSuccess,
  executeClaimExportSuccess,
  executeExceptionActionSuccess,
  executeTrustExportArtifactSuccess,
  openClaimDetailAuditTab,
  openExceptionDrawer,
  renderDetailRouter,
  renderMountedAuditExportFlow,
  renderMountedClaimExportFlow,
  renderMountedTrustEnvelopeDrawer,
  renderShell,
  resetLevel9HarnessState,
  resetViewport,
  seedShellAuth,
  setMobileViewport375,
  waitForDetailLoaded,
  waitForOutcomeStatus,
} from './level9.helpers';
import { GovernedActionControl } from '../actions/GovernedActionControl';

function resetAllActionClients() {
  resetIdempotencyStoreForTests();
  resetClaimExportTestMode();
  resetTrustActionTestMode();
  resetAuditExportTestMode();
  resetBudgetProposalTestMode();
  resetExceptionActionTestMode();
  resetSubsystemSafetyForTests();
  resetClaimDetailTestMode();
  resetDefaultTrustEnvelopeDetailClient();
  resetDefaultBudgetSimulationDetailClient();
  resetDefaultExceptionDetailClient();
}

function seedOwner() {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole('owner');
  setClaimDetailPolicyAuthorityForTests('proposal_required');
}

beforeEach(() => {
  resetLevel9HarnessState();
  resetAllActionClients();
  resetViewport();
});

describe('Level 9 Harness — Scope and integrity', () => {
  it('scope scan passes with zero violations', () => {
    const scan = runLevel9NegativeScopeScan();
    expect(scan.violations).toEqual([]);
  });

  it('all Level 9 flow markers exist', () => {
    const flows = assertLevel9FlowsExist();
    expect(flows.ok).toBe(true);
    expect(flows.missing).toEqual([]);
  });

  it('source integrity probes pass', () => {
    expect(runLevel9SourceIntegrityProbes().every((p) => p.ok)).toBe(true);
  });

  it('Level 8 scope scan remains clean for detail substrate', () => {
    const l8 = runLevel8NegativeScopeScan();
    expect(l8.violations.filter((v) => v.type === 'level10-leakage')).toEqual([]);
  });
});

describe('Level 9 Harness — Mounted execute-through-success (Iteration II)', () => {
  beforeEach(() => seedOwner());

  it('claim export confirms, succeeds, and shows artifact references', async () => {
    const user = userEvent.setup();
    await executeClaimExportSuccess(user);
    const outcome = document.querySelector('[data-level9-outcome-status="success"]');
    expect(outcome).toBeTruthy();
    expect(screen.getByText(/Artifact: artifact_claim_claim_0001/)).toBeInTheDocument();
    expect(screen.getByText(/Audit: aud_/)).toBeInTheDocument();
    expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy();
  });

  it('TrustEnvelope export report confirms without forensic hash fields', async () => {
    const user = userEvent.setup();
    await executeTrustExportArtifactSuccess(user);
    expect(screen.getByText(/Artifact: artifact_env_env_0001/)).toBeInTheDocument();
    expect(screen.getByText(/Audit:/)).toBeInTheDocument();
  });

  it('audit export confirms, shows reconstruction preview, and succeeds', async () => {
    const user = userEvent.setup();
    renderMountedAuditExportFlow();
    await waitFor(() => expect(document.querySelector('[data-audit-reconstruction-preview]')).toBeTruthy());
    expect(screen.getByText(/Hash chain:/)).toBeInTheDocument();
    expect(screen.getByText(/Excluded: email addresses/)).toBeInTheDocument();
    await confirmGovernedAction(user, /Export audit reconstruction/i);
    await waitForOutcomeStatus('success');
    expect(screen.getByText(/Artifact: artifact_audit/)).toBeInTheDocument();
    expect(screen.getByText(/Audit: aud_/)).toBeInTheDocument();
  });

  it('budget proposal confirms, shows preview, and succeeds as proposal-only', async () => {
    const user = userEvent.setup();
    renderShell('/app/budget/sim_0001');
    await waitForDetailLoaded('[data-budget-detail-loaded]');
    await waitFor(() => expect(document.querySelector('[data-proposal-preview]')).toBeTruthy());
    expect(screen.getByText(/No spend mutation/i)).toBeInTheDocument();
    await confirmGovernedAction(user, /Submit proposal/i);
    await waitForOutcomeStatus('success');
    expect(screen.getByText(/Proposal: prop_sim_0001/)).toBeInTheDocument();
    expect(screen.getByText(/Audit: aud_/)).toBeInTheDocument();
    expect(screen.queryByText(/spend updated/i)).toBeNull();
  });

  it.each([
    ['Acknowledge', /Acknowledge/i],
    ['Request more evidence', /Request more evidence/i],
    ['Mark disputed', /Mark disputed/i],
    ['Suppress similar', /Suppress similar low-risk alerts/i],
    ['Create proposal', /Create proposal/i],
  ] as const)('exception action %s executes through confirmation', async (_label, pattern) => {
    const user = userEvent.setup();
    await executeExceptionActionSuccess(user, pattern);
    expect(screen.getByText(/Action: exc_/)).toBeInTheDocument();
    expect(screen.getByText(/Audit: aud_action_/)).toBeInTheDocument();
  });
});

describe('Level 9 Harness — Mounted policy / permission / scope (Iteration II)', () => {
  it('viewer cannot export claim — button disabled with accessible reason', async () => {
    seedShellAuth('viewer');
    renderMountedClaimExportFlow();
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    const btn = screen.getByRole('button', { name: /Export verified report/i });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-describedby');
    assertNoFalseSuccessIdentifiers();
  });

  it('viewer cannot export trust report — button disabled', async () => {
    seedShellAuth('viewer');
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-trust-envelope-operator-view]')).toBeTruthy());
    await waitFor(() => {
      const exportButtons = screen.getAllByRole('button', { name: /Export report/i });
      expect(exportButtons.length).toBeGreaterThanOrEqual(1);
      exportButtons.forEach((button) => expect(button).toBeDisabled());
    });
    assertNoFalseSuccessIdentifiers();
  });

  it('blocked policy disables claim export with safe reason', async () => {
    seedOwner();
    renderMountedClaimExportFlow('claim_0001', 'v_claim_0001_1', 'blocked');
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    const btn = screen.getByRole('button', { name: /Export verified report/i });
    expect(btn).toBeDisabled();
    expect(btn.getAttribute('aria-label')).toMatch(/blocked|policy/i);
    assertNoFalseSuccessIdentifiers();
  });

  it('simulation_only policy disables claim export', async () => {
    seedOwner();
    renderMountedClaimExportFlow('claim_0001', 'v_claim_0001_1', 'simulation_only');
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    expect(screen.getByRole('button', { name: /Export verified report/i })).toBeDisabled();
  });

  it('mounted scope_denied after confirm shows safe copy without artifact', async () => {
    seedOwner();
    setClaimExportTestMode('cross_tenant');
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    await confirmGovernedAction(user, /Export verified report/i);
    await waitForOutcomeStatus('scope_denied');
    assertNoFalseSuccessIdentifiers();
  });

  it('blocked budget policy disables submit on mounted flow', async () => {
    seedOwner();
    setBudgetDetailPolicyAuthorityForTests('blocked');
    renderShell('/app/budget/sim_0001');
    await waitForDetailLoaded('[data-budget-detail-loaded]');
    expect(screen.getByRole('button', { name: /Submit proposal/i })).toBeDisabled();
  });
});

describe('Level 9 Harness — Mounted failure state matrix (Iteration II)', () => {
  beforeEach(() => seedOwner());

  it('confirmation_open renders dialog', async () => {
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    await user.click(screen.getByRole('button', { name: /Export verified report/i }));
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    expect(document.querySelector('[data-level9-confirmation]')?.closest('[role="dialog"]')).toBeTruthy();
  });

  it('pending disables duplicate activation with aria-busy', async () => {
    setClaimExportDelayForTests(400);
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    const trigger = screen.getByRole('button', { name: /Export verified report/i });
    await user.click(trigger);
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const panel = document.querySelector('[data-level9-confirmation]')!;
    const dialog = panel.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(dialog).getByRole('button', { name: /Export verified report/i }));
    await waitFor(() => expect(trigger).toHaveAttribute('aria-busy', 'true'));
    await waitForOutcomeStatus('success');
  });

  it.each([
    ['network_error', 'network_error'],
    ['audit_write_failed', 'audit_write_failed'],
    ['replay_rejected', 'replay_rejected'],
    ['scope_denied', 'scope_denied'],
  ] as const)('mounted claim/trust flow shows %s without false success', async (mode, status) => {
    const user = userEvent.setup();
    if (mode === 'scope_denied') {
      setClaimExportTestMode('cross_tenant');
      renderShell('/app/claims/claim_0001');
      await waitForDetailLoaded('[data-claim-detail-loaded]');
      await openClaimDetailAuditTab(user);
      await confirmGovernedAction(user, /Export verified report/i);
    } else {
      setClaimExportTestMode(mode === 'replay_rejected' ? 'replay' : mode);
      if (mode === 'replay_rejected') {
        const replayKey = generateIdempotencyKey('tenant_test_001', 'claim', 'claim_0001', 'export_verified_report');
        await exportVerifiedReport('tenant_test_001', 'claim_0001', 'v_claim_0001_1', replayKey);
      }
      renderShell('/app/claims/claim_0001');
      await waitForDetailLoaded('[data-claim-detail-loaded]');
      await openClaimDetailAuditTab(user);
      await confirmGovernedAction(user, /Export verified report/i);
    }
    await waitForOutcomeStatus(status);
    expect(document.querySelector(`[data-level9-outcome-status="${status}"]`)?.textContent).toBeTruthy();
    if (status !== 'success') assertNoFalseSuccessIdentifiers();
  });

  it('mounted audit export access_denied fails closed', async () => {
    setAuditExportTestMode('access_denied');
    const user = userEvent.setup();
    renderMountedAuditExportFlow();
    await confirmGovernedAction(user, /Export audit reconstruction/i);
    await waitForOutcomeStatus('permission_denied');
    assertNoFalseSuccessIdentifiers();
  });

  it('mounted audit export corrupted artifact fails closed', async () => {
    setAuditExportTestMode('corrupted_artifact');
    const user = userEvent.setup();
    renderMountedAuditExportFlow();
    await confirmGovernedAction(user, /Export audit reconstruction/i);
    await waitForOutcomeStatus('artifact_unavailable');
    assertNoFalseSuccessIdentifiers();
  });
});

describe('Level 9 Harness — Mounted idempotency and replay (Iteration II)', () => {
  beforeEach(() => seedOwner());

  it('double-click confirm on claim export invokes client once', async () => {
    const spy = vi.spyOn(claimExportModule, 'exportVerifiedReport');
    const user = userEvent.setup();
    setClaimExportDelayForTests(300);
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    await user.click(screen.getByRole('button', { name: /Export verified report/i }));
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const panel = document.querySelector('[data-level9-confirmation]')!;
    const dialog = panel.closest('[role="dialog"]') as HTMLElement;
    const confirm = within(dialog).getByRole('button', { name: /Export verified report/i });
    await user.dblClick(confirm);
    await waitForOutcomeStatus('success');
    expect(spy.mock.calls.length).toBeLessThanOrEqual(1);
    spy.mockRestore();
  });

  it('Enter-repeat on budget proposal confirm does not duplicate proposal', async () => {
    const user = userEvent.setup();
    renderShell('/app/budget/sim_0001');
    await waitForDetailLoaded('[data-budget-detail-loaded]');
    await user.click(screen.getByRole('button', { name: /Submit proposal/i }));
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const panel = document.querySelector('[data-level9-confirmation]')!;
    const dialog = panel.closest('[role="dialog"]') as HTMLElement;
    const confirm = within(dialog).getByRole('button', { name: /Submit proposal/i });
    confirm.focus();
    await user.keyboard('{Enter}{Enter}');
    await waitForOutcomeStatus('success');
    expect(screen.getAllByText(/Proposal: prop_sim_0001/).length).toBe(1);
  });

  it('rapid exception acknowledge click does not duplicate action outcome', async () => {
    const user = userEvent.setup();
    await openExceptionDrawer(user);
    await user.click(screen.getByRole('button', { name: /^Acknowledge$/i }));
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const panel = document.querySelector('[data-level9-confirmation]')!;
    const dialog = panel.closest('[role="dialog"]') as HTMLElement;
    const confirm = within(dialog).getByRole('button', { name: /^Acknowledge$/i });
    await user.dblClick(confirm);
    await waitForOutcomeStatus('success');
    expect(screen.getAllByText(/Action: exc_/).length).toBe(1);
  });

  it('replay after success shows replay_rejected without new artifact', async () => {
    const user = userEvent.setup();
    await executeClaimExportSuccess(user);
    setClaimExportTestMode('replay');
    await confirmGovernedAction(user, /Export verified report/i);
    await waitForOutcomeStatus('replay_rejected');
  });
});

describe('Level 9 Harness — Exception actions client coverage (Iteration II)', () => {
  beforeEach(() => seedOwner());

  it.each([
    ['acknowledge', acknowledgeException],
    ['request_more_evidence', requestMoreEvidence],
    ['mark_disputed', markDisputed],
    ['suppress_similar', suppressSimilarAlerts],
    ['create_proposal', createProposal],
  ] as const)('%s returns actionId and auditEventId for exc_0001', async (_kind, fn) => {
    const outcome = await fn('tenant_test_001', 'exc_0001', 'v_exc_0001_1');
    expect(outcome.status).toBe('success');
    expect(outcome.objectId).toBe('exc_0001');
    expect(outcome.actionId).toBeTruthy();
    expect(outcome.auditEventId).toBeTruthy();
  });

  it('suppress similar includes scope explanation in client copy', async () => {
    const outcome = await suppressSimilarAlerts('tenant_test_001', 'exc_0001', 'v_exc_0001_1');
    expect(outcome.safeUserCopy).toMatch(/scope|similar|low-risk/i);
  });

  it('create proposal returns proposalId only, not spend mutation', async () => {
    const outcome = await createProposal('tenant_test_001', 'exc_0001', 'v_exc_0001_1');
    expect(outcome.proposalId).toMatch(/^prop_exc_/);
    expect(outcome.safeUserCopy).not.toMatch(/spend updated/i);
  });
});

describe('Level 9 Harness — TrustEnvelope export artifact client', () => {
  beforeEach(() => seedOwner());

  it('exportArtifact returns audit reference in safe copy', async () => {
    const outcome = await exportArtifact('tenant_test_001', 'env_0001', 'v_env_0001_1');
    expect(outcome.status).toBe('success');
    expect(outcome.safeUserCopy).toMatch(/AUD-2026-07-02-004182/i);
    expect(outcome.artifactRef).toBeTruthy();
    expect(outcome.auditEventId).toBeTruthy();
    expect(outcome.artifact?.semanticTruthHash).toBe('');
    expect(outcome.artifact?.artifactHash).toBe('');
    expect(outcome.artifact?.signatureHash).toBeNull();
  });

  it('replay rejects duplicate export artifact', async () => {
    const key = generateIdempotencyKey('tenant_test_001', 'trust_envelope', 'env_0001', 'export_artifact');
    const first = await exportArtifact('tenant_test_001', 'env_0001', 'v_env_0001_1', key);
    expect(first.status).toBe('success');
    setTrustActionTestMode('replay');
    const second = await exportArtifact('tenant_test_001', 'env_0001', 'v_env_0001_1', key);
    expect(second.status).toBe('replay_rejected');
  });
});

describe('Level 9 Harness — Shared action contract', () => {
  beforeEach(() => seedOwner());

  it('claim export client probe returns auditEventId and artifactRef on success', async () => {
    const probe = await runLevel9ClientProbe();
    expect(probe.ok).toBe(true);
    expect(probe.outcome.auditEventId).toBeTruthy();
    expect(probe.outcome.artifactRef).toBeTruthy();
  });

  it('exportVerifiedReport returns safe copy with incrementality boundary', async () => {
    const outcome = await exportVerifiedReport('tenant_test_001', 'claim_0001', 'v_claim_0001_1');
    expect(outcome.status).toBe('success');
    expect(outcome.safeUserCopy).toMatch(/incrementality|Verified report exported/i);
  });
});

describe('Level 9 Harness — Client policy / permission / scope', () => {
  beforeEach(() => {
    establishTenant(createMockSession(), createMockTenant());
    setBootstrapReady();
  });

  it('viewer cannot export claim report', async () => {
    setCurrentUserRole('viewer');
    const outcome = await exportVerifiedReport('tenant_test_001', 'claim_0001', 'v_claim_0001_1');
    expect(outcome.status).toBe('permission_denied');
  });

  it('billing_only cannot export trust artifact via permission gate', async () => {
    setCurrentUserRole('billing_only');
    const outcome = await exportArtifact('tenant_test_001', 'env_0001', 'v_env_0001_1');
    expect(outcome.status).toBe('permission_denied');
  });

  it('blocked budget policy prevents proposal submit', async () => {
    setCurrentUserRole('owner');
    setBudgetProposalTestMode('blocked_policy');
    const outcome = await submitBudgetProposal('tenant_test_001', 'sim_0001', 'v_sim_0001_1');
    expect(outcome.status).toBe('blocked_by_policy');
  });

  it('cross-tenant claim export is scope denied', async () => {
    setCurrentUserRole('owner');
    setClaimExportTestMode('cross_tenant');
    const outcome = await exportVerifiedReport('tenant_test_001', 'claim_0001', 'v_claim_0001_1');
    expect(outcome.status).toBe('scope_denied');
  });
});

describe('Level 9 Harness — Audit and budget client', () => {
  beforeEach(() => seedOwner());

  it('audit export returns artifactRef and auditEventId', async () => {
    const outcome = await exportAuditReconstruction('tenant_test_001', {}, null);
    expect(outcome.status).toBe('success');
    expect(outcome.artifactRef).toBeTruthy();
    expect(outcome.auditEventId).toBeTruthy();
  });

  it('budget proposal creates proposalId without spend mutation copy', async () => {
    const outcome = await submitBudgetProposal('tenant_test_001', 'sim_0001', 'v_sim_0001_1');
    expect(outcome.status).toBe('success');
    expect(outcome.proposalId).toMatch(/^prop_/);
    expect(outcome.safeUserCopy).toMatch(/No spend was executed|Proposal/i);
  });
});

describe('Level 9 Harness — Client idempotency', () => {
  beforeEach(() => seedOwner());

  it('double export with same idempotency key rejects replay', async () => {
    const key = 'idem_fixed_claim_export';
    const first = await exportVerifiedReport('tenant_test_001', 'claim_0001', 'v_claim_0001_1', key);
    expect(first.status).toBe('success');
    setClaimExportTestMode('replay');
    const second = await exportVerifiedReport('tenant_test_001', 'claim_0001', 'v_claim_0001_1', key);
    expect(second.status).toBe('replay_rejected');
  });
});

describe('Level 9 Harness — Kill switch and degraded state (Iteration II)', () => {
  beforeEach(() => seedOwner());

  it.each([
    ['trust_api_paused', { trust_api_paused: true }, null],
    ['export_unavailable', { export_unavailable: true }, null],
    ['audit_write_unavailable', { audit_write_unavailable: true }, null],
    ['policy_unavailable', { policy_unavailable: true }, null],
    ['integration_degraded', { integration_degraded: true }, 'integration_attention' as const],
  ] as const)('subsystem %s blocks claim export client', async (_name, flags, health) => {
    if (health) setSubsystemHealthForTests(health);
    setSubsystemBlockForTests(flags);
    const outcome = await exportVerifiedReport('tenant_test_001', 'claim_0001', 'v_claim_0001_1');
    expect(outcome.status).toBe('subsystem_unsafe');
  });

  it.each([
    ['export_unavailable', /Export verified report/i, 'claim-export'] as const,
    ['export_unavailable', /Export report/i, 'channel-trust'] as const,
  ])('mounted %s disables action while detail remains visible', async (flag, buttonName, surface) => {
    setSubsystemBlockForTests({ [flag]: true });
    if (surface === 'claim-export') {
      renderMountedClaimExportFlow();
      await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    } else {
      renderMountedTrustEnvelopeDrawer('env_0001');
      await waitFor(() => expect(document.querySelector('[data-trust-envelope-operator-view]')).toBeTruthy());
    }
    await waitFor(() => expect(screen.getByRole('button', { name: buttonName })).toBeDisabled());
  });
});

describe('Level 9 Harness — Artifact boundedness behavioral (Iteration II)', () => {
  beforeEach(() => seedOwner());

  it('declared export preview byte limit matches contract', () => {
    expect(MAX_EXPORT_PREVIEW_BYTES).toBe(32_768);
    expect(MAX_COPY_JSON_BYTES).toBe(65_536);
  });

  it('claim export preview DOM nodes remain under cap', async () => {
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    await waitFor(() => expect(document.querySelector('[data-export-preview]')).toBeTruthy());
    assertPreviewDomBounded('[data-export-preview]');
  });

  it('audit reconstruction preview DOM nodes remain under cap', async () => {
    renderMountedAuditExportFlow();
    await waitFor(() => expect(document.querySelector('[data-audit-reconstruction-preview]')).toBeTruthy());
    assertPreviewDomBounded('[data-audit-reconstruction-preview]');
  });
});

describe('Level 9 Harness — Accessibility and mobile (Iteration II)', () => {
  beforeEach(() => seedOwner());

  it('claim export confirmation focus trap wraps Tab and Shift+Tab', async () => {
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    const trigger = screen.getByRole('button', { name: /Export verified report/i });
    trigger.focus();
    await user.click(trigger);
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const panel = document.querySelector('[data-level9-confirmation]')!;
    const dialog = panel.closest('[role="dialog"]') as HTMLElement;
    const buttons = within(dialog).getAllByRole('button');
    const last = buttons[buttons.length - 1];
    last.focus();
    await user.keyboard('{Tab}');
    expect(buttons[0]).toHaveFocus();
    buttons[0].focus();
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(last).toHaveFocus();
  });

  it('focus restores to claim export trigger after modal close via cancel', async () => {
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    const trigger = screen.getByRole('button', { name: /Export verified report/i });
    trigger.focus();
    await user.click(trigger);
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const panel = document.querySelector('[data-level9-confirmation]')!;
    const dialog = panel.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(dialog).getByRole('button', { name: /Cancel/i }));
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeNull());
    expect(trigger).toHaveFocus();
  });

  it('success outcome is announced via aria-live region', async () => {
    const user = userEvent.setup();
    await executeClaimExportSuccess(user);
    const live = document.querySelector('[data-level9-outcome][aria-live="polite"]');
    expect(live).toBeTruthy();
    expect(live?.textContent).toMatch(/Verified report exported/i);
  });

  it.each([
    ['claim-export-flow', '[data-claim-export-flow]', /Export verified report/i],
    ['channel-trust-export', '[data-trust-envelope-actions]', /Export report/i],
    ['audit-export-flow', '[data-audit-export-flow]', /Export audit reconstruction/i],
    ['/app/budget/sim_0001', '[data-budget-proposal-flow]', /Submit proposal/i],
  ] as const)('375px %s action flow remains usable', async (path, marker, buttonPattern) => {
    setMobileViewport375();
    const user = userEvent.setup();
    if (path === 'audit-export-flow') {
      renderMountedAuditExportFlow();
    } else if (path === 'claim-export-flow') {
      renderMountedClaimExportFlow();
      await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    } else if (path === 'channel-trust-export') {
      renderMountedTrustEnvelopeDrawer('env_0001');
      await waitFor(() => expect(document.querySelector('[data-trust-envelope-operator-view]')).toBeTruthy());
    } else {
      renderShell(path);
      await waitForDetailLoaded('[data-budget-detail-loaded]');
    }
    expect(document.querySelector(marker)).toBeTruthy();
    expect(screen.getByRole('button', { name: buttonPattern })).toBeInTheDocument();
  });

  it('375px exception drawer actions remain usable', async () => {
    setMobileViewport375();
    const user = userEvent.setup();
    await openExceptionDrawer(user);
    expect(screen.getByRole('button', { name: /^Acknowledge$/i })).toBeInTheDocument();
  });
});

describe('Level 9 Harness — Sabotage controls (Iteration II)', () => {
  it('clean product source passes source sabotage probes', () => {
    const triggered = runLevel9SourceSabotageProbes().filter((p) => p.triggered);
    expect(triggered).toEqual([]);
  });

  it('poisoned sample triggers sabotage detectors', () => {
    const poison = 'claim verified solely because signature passed\nspend updated\nTrust Command Center content';
    const triggered = runLevel9SabotageProbes(poison).filter((p) => p.triggered);
    expect(triggered.length).toBeGreaterThan(0);
  });

  it('privacy scan passes on repository', () => {
    const privacy = runPrivacyScan();
    expect(privacy.violations).toEqual([]);
  });

  it('secret scan passes on src actions', () => {
    const secret = runSecretScan();
    expect(secret.violations).toEqual([]);
  });
});

describe('Level 9 Harness — Durability, navigation, clipboard (Iteration III)', () => {
  beforeEach(() => seedOwner());

  it('hard refresh preserves completed outcome from session registry', async () => {
    const user = userEvent.setup();
    const view = renderMountedClaimExportFlow();
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    await confirmGovernedAction(user, /Export verified report/i);
    await waitForOutcomeStatus('success');
    simulateHardRefreshForTests();
    view.unmount();
    renderMountedClaimExportFlow();
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    await waitFor(() => expect(document.querySelector('[data-level9-outcome-status="success"]')).toBeTruthy());
  });

  it('hard refresh preserves pending registry state during delayed export', async () => {
    setClaimExportDelayForTests(800);
    const user = userEvent.setup();
    const view = renderMountedClaimExportFlow();
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    const trigger = screen.getByRole('button', { name: /Export verified report/i });
    await user.click(trigger);
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const panel = document.querySelector('[data-level9-confirmation]')!;
    const dialog = panel.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(dialog).getByRole('button', { name: /Export verified report/i }));
    await waitFor(() => expect(trigger).toHaveAttribute('aria-busy', 'true'));
    simulateHardRefreshForTests();
    view.unmount();
    renderMountedClaimExportFlow();
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Export verified report/i })).toHaveAttribute('aria-busy', 'true'),
    );
  });

  it('route unmount during pending recovers pending on return', async () => {
    setClaimExportDelayForTests(800);
    const user = userEvent.setup();
    const router = createClaimExportNavRouter(['/other', '/export'], 1);
    renderDetailRouter(router);
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    const trigger = screen.getByRole('button', { name: /Export verified report/i });
    await user.click(trigger);
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const panel = document.querySelector('[data-level9-confirmation]')!;
    const dialog = panel.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(dialog).getByRole('button', { name: /Export verified report/i }));
    await waitFor(() => expect(trigger).toHaveAttribute('aria-busy', 'true'));
    router.navigate('/other');
    await waitFor(() => expect(document.querySelector('[data-other-page]')).toBeTruthy());
    router.navigate('/export');
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Export verified report/i })).toHaveAttribute('aria-busy', 'true'),
    );
  });

  it('history back during confirmation allows resubmit after return', async () => {
    const user = userEvent.setup();
    const router = createClaimExportNavRouter(['/other', '/export'], 1);
    renderDetailRouter(router);
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    await user.click(screen.getByRole('button', { name: /Export verified report/i }));
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    router.navigate(-1);
    await waitFor(() => expect(document.querySelector('[data-other-page]')).toBeTruthy());
    router.navigate(1);
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeNull());
    await confirmGovernedAction(user, /Export verified report/i, /Export verified report/i);
    await waitFor(
      () => expect(document.querySelector('[data-level9-outcome-status="success"]')).toBeTruthy(),
      { timeout: 5000 },
    );
  }, 10000);

  it('destructive confirmation modal ignores Escape', async () => {
    const user = userEvent.setup();
    renderMountedClaimExportFlow();
    await waitFor(() => expect(document.querySelector('[data-claim-export-flow]')).toBeTruthy());
    await user.click(screen.getByRole('button', { name: /Export verified report/i }));
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    await user.keyboard('{Escape}');
    expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy();
  });

  it('standard confirmation modal closes on Escape', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <GovernedActionControl
        actionLabel="Test action"
        policyAuthority="proposal_required"
        disabled={false}
        phase="confirmation_open"
        outcome={null}
        confirmationTitle="Confirm test"
        confirmationBody={<p>Body</p>}
        destructive={false}
        onOpen={vi.fn()}
        onConfirm={vi.fn()}
        onCancel={onCancel}
        showToast={false}
        onDismissToast={vi.fn()}
      />,
    );
    await user.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalled();
  });

  it.each([
    ['timeout', 'timeout'],
    ['partial_failure', 'partial_failure'],
  ] as const)('mounted claim export shows %s outcome', async (mode, status) => {
    setClaimExportTestMode(mode);
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    await confirmGovernedAction(user, /Export verified report/i);
    await waitForOutcomeStatus(status);
    if (status !== 'partial_failure') assertNoFalseSuccessIdentifiers();
  });

  it('mounted budget proposal shows stale_object_conflict', async () => {
    setBudgetProposalTestMode('stale');
    const user = userEvent.setup();
    renderShell('/app/budget/sim_0001');
    await waitForDetailLoaded('[data-budget-detail-loaded]');
    await confirmGovernedAction(user, /Submit proposal/i);
    await waitForOutcomeStatus('conflict_stale_object');
    assertNoFalseSuccessIdentifiers();
  });

  it('network_error retry succeeds on second mounted attempt', async () => {
    setClaimExportTestMode('network_error');
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0001');
    await waitForDetailLoaded('[data-claim-detail-loaded]');
    await openClaimDetailAuditTab(user);
    await confirmGovernedAction(user, /Export verified report/i);
    await waitForOutcomeStatus('network_error');
    resetClaimExportTestMode();
    await confirmGovernedAction(user, /Export verified report/i);
    await waitForOutcomeStatus('success');
  });

  it('export artifact success is announced via aria-live region', async () => {
    const user = userEvent.setup();
    await executeTrustExportArtifactSuccess(user);
    const live = document.querySelector('[data-level9-outcome][aria-live="polite"]');
    expect(live).toBeTruthy();
    expect(live?.textContent).toMatch(/Artifact artifact_env_env_0001/i);
  });

  it('stable idempotency key derives from tenant object action fingerprint', () => {
    const a = generateIdempotencyKey('tenant_test_001', 'claim', 'claim_0001', 'export_verified_report');
    const b = generateIdempotencyKey('tenant_test_001', 'claim', 'claim_0001', 'export_verified_report');
    expect(a).toBe(b);
    expect(a).toMatch(/^idem_tenant_test_001:claim:claim_0001:export_verified_report:v1$/);
  });
});

describe('Level 9 Harness — Canonical JSON', () => {
  it('canonical JSON sorts provenance chain deterministically', () => {
    const contract = buildMinimalTrustEnvelopeJsonContract({
      provenanceChain: [
        {
          timestamp: '2026-07-02T13:00:00Z',
          eventType: 'Later',
          source: 'Stripe',
          result: 'r',
          evidenceReference: 'EV-Z',
        },
        {
          timestamp: '2026-07-02T12:00:00Z',
          eventType: 'Earlier',
          source: 'Shopify',
          result: 'r',
          evidenceReference: 'EV-A',
        },
      ],
    });
    const json = buildCanonicalTrustEnvelopeJson(contract);
    expect(json.indexOf('"eventType": "Earlier"')).toBeLessThan(json.indexOf('"eventType": "Later"'));
  });
});
