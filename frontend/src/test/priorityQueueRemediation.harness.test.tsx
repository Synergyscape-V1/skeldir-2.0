import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import { COMMAND_CENTER_COPY } from '../commandCenter/copy';
import { buildTriageHref, parseTriageSearch } from '../commandCenter/triageHref';
import {
  beginTriageSession,
  countBlockingIssues,
  getNextUnresolvedTriageIssue,
  getTriageQueueSnapshot,
  markTriageIssueResolved,
  resetTriageQueueSession,
} from '../commandCenter/triageQueueStore';
import { COMMAND_CENTER_PRIORITY_ISSUES } from '../commandCenter/commandCenterPriorityFixtures';
import { resolvePrimaryAction } from '../commandCenter/commandCenterClient';
import {
  renderCommandCenter,
  resetLevel10HarnessState,
  seedShellAuth,
  waitForCommandCenterLoaded,
  screen,
} from './level10.helpers';
import { renderShell, resetLevel9HarnessState, seedShellAuth as seedL9 } from './level9.helpers';
import { resetBudgetProposalTestMode } from '../actions/budgetProposalClient';
import { resetDefaultBudgetSimulationDetailClient } from '../budget/budgetSimulationDetailClient';

beforeEach(() => {
  resetLevel10HarnessState();
  resetLevel9HarnessState();
  resetBudgetProposalTestMode();
  resetDefaultBudgetSimulationDetailClient();
  resetTriageQueueSession();
  vi.useRealTimers();
});

describe('CDO Priority Queue Remediation — Audit 1 (PriorityQueue primitive)', () => {
  it('banner uses blocking-budget copy with visible multiplicity', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(screen.getByText(COMMAND_CENTER_COPY.urgencyCopy(3))).toBeInTheDocument();
    expect(document.querySelector('[data-command-center-urgency]')?.textContent).not.toMatch(
      /require review before action is safe/i,
    );
  });

  it('primary CTA is Review issues (N) and opens the PriorityQueue modal', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    const action = resolvePrimaryAction(
      {
        tenantId: 't',
        lastUpdatedAt: new Date().toISOString(),
        freshness: 'fresh',
        healthState: 'operational',
        trustApiReadFailed: false,
        killSwitchActive: false,
        hasTrustEnvelope: true,
        latestEnvelopeId: 'env_0001',
        summaryMetrics: [],
        priorityIssues: COMMAND_CENTER_PRIORITY_ISSUES,
        trendPoints: [],
        channelRows: [],
        recentEnvelopes: [],
        recentEnvelopesSignalWindow: '24h',
        auditActivity: [],
        openExceptionsCount: 0,
        claimsReconciledCount: 0,
        sourceTrace: {},
      },
      3,
    );
    expect(action.kind).toBe('review_issues');
    expect(action.href).toBeUndefined();

    const cta = screen.getByRole('button', { name: COMMAND_CENTER_COPY.reviewIssues(3) });
    await user.click(cta);
    await waitFor(() => expect(document.querySelector('[data-priority-queue-modal], [data-priority-queue-drawer]')).toBeTruthy());
    expect(document.querySelectorAll('[data-priority-modal-issue], [data-priority-drawer-issue]').length).toBe(3);
    expect(document.querySelector('[data-modal-panel]')).toBeTruthy();
    expect(document.querySelector('[data-drawer-panel]')).toBeNull();
  });

  it('queue rows expose triage source params (no orphan deep-link)', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    await user.click(screen.getByRole('button', { name: COMMAND_CENTER_COPY.reviewIssues(3) }));
    await waitFor(() => expect(document.querySelector('[data-priority-queue-modal]')).toBeTruthy());
    const href = document
      .querySelector('[data-top-priority-issue] [data-priority-action-href]')
      ?.getAttribute('data-priority-action-href');
    expect(href).toContain('source=command_center_queue');
    expect(href).toContain('issueId=pri_policy_meta_budget');
    const parsed = parseTriageSearch(new URL(href!, 'https://skeldir.local').searchParams);
    expect(parsed.isTriage).toBe(true);
  });

  it('resolving an issue decrements the blocking banner count', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    beginTriageSession(COMMAND_CENTER_PRIORITY_ISSUES);
    markTriageIssueResolved('pri_policy_meta_budget', 'Budget policy approved. 2 issues remain.');
    expect(countBlockingIssues(COMMAND_CENTER_PRIORITY_ISSUES)).toBe(2);

    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(screen.getByText(COMMAND_CENTER_COPY.urgencyCopy(2))).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: COMMAND_CENTER_COPY.reviewIssues(2) }));
    await waitFor(() => expect(document.querySelector('[data-priority-queue-modal]')).toBeTruthy());
    expect(document.querySelector('[data-priority-issue="pri_policy_meta_budget"]')?.getAttribute('data-priority-resolved')).toBe(
      'true',
    );
  });

  it('all resolved yields All clear completion disposition', async () => {
    seedShellAuth();
    beginTriageSession(COMMAND_CENTER_PRIORITY_ISSUES);
    for (const issue of COMMAND_CENTER_PRIORITY_ISSUES) {
      markTriageIssueResolved(issue.id);
    }
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(screen.getByText(COMMAND_CENTER_COPY.urgencyAllClear)).toBeInTheDocument();
    expect(document.querySelector('[data-urgency-all-clear]')).toBeTruthy();
    expect(document.querySelector('[data-primary-action-kind="go_to_budget"]')).toBeTruthy();
  });
});

describe('CDO Priority Queue Remediation — Audit 2 (Sequential Triage Node)', () => {
  it('budget detail adopts TriageContextHeader when source=command_center_queue', async () => {
    seedL9();
    const href = buildTriageHref(
      '/app/budget/sim_0002?focus=policy',
      'pri_policy_meta_budget',
      1,
      3,
    );
    beginTriageSession(COMMAND_CENTER_PRIORITY_ISSUES);
    renderShell(href);
    await waitFor(() => expect(document.querySelector('[data-budget-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-budget-triage-mode="true"]')).toBeTruthy();
    expect(document.querySelector('[data-triage-context-header]')).toBeTruthy();
    expect(document.querySelector('[data-triage-progress]')?.textContent).toMatch(/Issue 1 of 3/i);
    expect(document.querySelector('[data-budget-proposal-triage="true"]')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Approve & Advance/i })).toBeInTheDocument();
  });

  it('standalone budget detail keeps Submit proposal (no triage chrome)', async () => {
    seedL9();
    renderShell('/app/budget/sim_0001');
    await waitFor(() => expect(document.querySelector('[data-budget-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-budget-triage-mode="true"]')).toBeNull();
    expect(document.querySelector('[data-triage-context-header]')).toBeNull();
    expect(screen.getByRole('button', { name: /Submit proposal/i })).toBeInTheDocument();
  });

  it('Approve & Advance success marks resolved and routes to next queue item', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    seedL9();
    beginTriageSession(COMMAND_CENTER_PRIORITY_ISSUES);
    const href = buildTriageHref(
      '/app/budget/sim_0002?focus=policy',
      'pri_policy_meta_budget',
      1,
      3,
    );
    const { router } = renderShell(href);
    await waitFor(() => expect(document.querySelector('[data-budget-detail-loaded]')).toBeTruthy());

    await user.click(screen.getByRole('button', { name: /Approve & Advance/i }));
    await waitFor(() => expect(document.querySelector('[data-level9-confirmation]')).toBeTruthy());
    const confirmButtons = screen.getAllByRole('button', { name: /^Approve & Advance$/i });
    await user.click(confirmButtons[confirmButtons.length - 1]!);

    await waitFor(() => expect(document.querySelector('[data-post-action-overlay]')).toBeTruthy());
    expect(getTriageQueueSnapshot().resolvedIds).toContain('pri_policy_meta_budget');
    expect(getNextUnresolvedTriageIssue('pri_policy_meta_budget')?.id).toBe('pri_google_discrepancy');

    await vi.advanceTimersByTimeAsync(1600);
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/app/claims/claim_0010');
      expect(router.state.location.search).toContain('source=command_center_queue');
      expect(router.state.location.search).toContain('issueId=pri_google_discrepancy');
    });
  });

  it('claim triage node exposes Mark reviewed & Advance', async () => {
    seedL9();
    beginTriageSession(COMMAND_CENTER_PRIORITY_ISSUES);
    const href = buildTriageHref('/app/claims/claim_0010', 'pri_google_discrepancy', 2, 3);
    renderShell(href);
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-claim-triage-mode="true"]')).toBeTruthy();
    expect(document.querySelector('[data-triage-context-header]')).toBeTruthy();
    expect(screen.getByRole('button', { name: COMMAND_CENTER_COPY.triage.markReviewedAndAdvance })).toBeInTheDocument();
  });
});

describe('CDO Priority Queue Remediation — negative / fail-closed', () => {
  it('malformed triage params do not activate triage chrome', async () => {
    seedL9();
    renderShell('/app/budget/sim_0002?source=command_center_queue&issueId=&issueIndex=abc');
    await waitFor(() => expect(document.querySelector('[data-budget-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-triage-context-header]')).toBeNull();
    expect(document.querySelector('[data-budget-triage-mode="true"]')).toBeNull();
  });

  it('singular Review top issue is not the primary supervisory CTA', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(screen.queryByRole('link', { name: COMMAND_CENTER_COPY.reviewTopIssue })).toBeNull();
    expect(screen.queryByRole('button', { name: COMMAND_CENTER_COPY.reviewTopIssue })).toBeNull();
  });
});
