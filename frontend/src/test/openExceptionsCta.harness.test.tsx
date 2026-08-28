import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  openExceptionsCtaSabotageFixture,
  scanOpenExceptionsCta,
} from '../audit/openExceptionsCtaScan';
import { COMMAND_CENTER_COPY } from '../commandCenter/copy';
import { buildSummaryMetrics, countHumanMeaningfulTrustIssues } from '../commandCenter/summaryMetrics';
import { COMMAND_CENTER_PRIORITY_ISSUES } from '../commandCenter/commandCenterPriorityFixtures';
import {
  renderCommandCenter,
  resetLevel10HarnessState,
  seedShellAuth,
  waitForCommandCenterLoaded,
  screen,
} from './level10.helpers';

beforeEach(() => {
  resetLevel10HarnessState();
});

describe('CRHAID 1 — Open exceptions CTA → Exceptions queue', () => {
  describe('Positive controls', () => {
    it('copy + metrics resolve open_exceptions to /app/exceptions', () => {
      expect(COMMAND_CENTER_COPY.summaryDrilldown.open_exceptions.href).toBe('/app/exceptions');

      const metrics = buildSummaryMetrics({
        claimsRows: [],
        verifiedRevenueMinor: 0n,
        trendPoints: [],
        priorityIssues: COMMAND_CENTER_PRIORITY_ISSUES,
        killSwitchActive: false,
      });
      const openExceptions = metrics.find((m) => m.id === 'open_exceptions');
      expect(countHumanMeaningfulTrustIssues(COMMAND_CENTER_PRIORITY_ISSUES)).toBe(1);
      expect(openExceptions?.drillDownHref).toBe('/app/exceptions');
      expect(openExceptions?.drillDownLabel).toBe('Review blocking issues');
      if (openExceptions?.tileKind === 'supervisory_health') {
        expect(openExceptions.displayValue).toBe('1 Critical Discrepancy');
      }
    });

    it('zero trust-issues state still drills to Exceptions queue (never Overview)', () => {
      const metrics = buildSummaryMetrics({
        claimsRows: [],
        verifiedRevenueMinor: 0n,
        trendPoints: [],
        priorityIssues: [],
        killSwitchActive: false,
      });
      const openExceptions = metrics.find((m) => m.id === 'open_exceptions');
      expect(openExceptions?.drillDownHref).toBe('/app/exceptions');
      if (openExceptions?.tileKind === 'supervisory_health') {
        expect(openExceptions.displayValue).toBe('0 Trust Issues');
      }
    });

    it('DOM drill-down href is /app/exceptions and navigates off Overview', async () => {
      const user = userEvent.setup();
      seedShellAuth();
      const { router } = renderCommandCenter('/app');
      await waitForCommandCenterLoaded();

      const drilldown = document.querySelector('[data-summary-drilldown="open_exceptions"]');
      expect(drilldown?.getAttribute('href')).toBe('/app/exceptions');
      expect(screen.getByText('1 Critical Discrepancy')).toBeInTheDocument();

      await user.click(drilldown as HTMLElement);
      await waitFor(() => {
        expect(router.state.location.pathname).toBe('/app/exceptions');
      });
      expect(router.state.location.pathname).not.toBe('/app');
      await waitFor(() => {
        expect(document.querySelector('[data-exceptions-page]')).toBeTruthy();
      });
    });

    it('static integrity scan passes on live sources', () => {
      expect(scanOpenExceptionsCta()).toEqual([]);
    });
  });

  describe('Negative controls', () => {
    it('Overview self-loop /app is rejected by scan', () => {
      const sabotage = openExceptionsCtaSabotageFixture();
      const violations = scanOpenExceptionsCta(sabotage);
      expect(violations.some((v) => v.rule === 'overview-self-loop')).toBe(true);
      expect(violations.some((v) => v.rule === 'legacy-priority-queue-anchor')).toBe(true);
      expect(violations.some((v) => v.rule === 'drilldown-not-sourced-from-copy')).toBe(true);
    });
  });

  describe('Meta-negative control', () => {
    it('harness fails when live copy is sabotaged to /app (non-vacuous)', () => {
      expect(scanOpenExceptionsCta()).toEqual([]);

      const sabotaged = scanOpenExceptionsCta(openExceptionsCtaSabotageFixture());
      expect(sabotaged.length).toBeGreaterThan(0);
      expect(sabotaged.some((v) => v.rule === 'overview-self-loop')).toBe(true);
    });
  });
});
