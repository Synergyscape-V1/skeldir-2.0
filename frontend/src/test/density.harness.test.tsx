import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { BenchmarksPage } from '../components/benchmarks/BenchmarksPage/BenchmarksPage';
import { AuthenticatedAppShell } from '../components/shell/AuthenticatedAppShell/AuthenticatedAppShell';
import { compactDensityReductionRatio, runDensityTokenAudit } from '../audit/densityAudit';
import { seedShellAuth } from './level9.helpers';

describe('Enterprise compact density harness', () => {
  it('density token audit passes with zero violations', () => {
    const { violations, checksRun } = runDensityTokenAudit();
    expect(violations).toEqual([]);
    expect(checksRun).toBeGreaterThanOrEqual(16);
  });

  it('compact profile yields measurable row-height reduction', () => {
    const { verticalReductionPercent } = compactDensityReductionRatio();
    expect(verticalReductionPercent).toBeGreaterThanOrEqual(30);
  });

  it('authenticated shell applies enterprise-compact density by default', async () => {
    seedShellAuth('owner');
    render(
      <MemoryRouter initialEntries={['/app/benchmarks']}>
        <Routes>
          <Route path="/app" element={<AuthenticatedAppShell />}>
            <Route path="benchmarks" element={<BenchmarksPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(document.querySelector('[data-authenticated-app-shell]')).toBeInTheDocument());
    expect(document.querySelector('[data-authenticated-app-shell]')?.getAttribute('data-density')).toBe(
      'enterprise-compact',
    );
  });

  it('onboarding routes retain comfortable density', () => {
    seedShellAuth('owner');
    render(
      <MemoryRouter initialEntries={['/app/onboarding/step/1']}>
        <Routes>
          <Route path="/app" element={<AuthenticatedAppShell />}>
            <Route path="onboarding/step/:step" element={<div data-onboarding-step>step</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(document.querySelector('[data-authenticated-app-shell]')?.getAttribute('data-density')).toBe('comfortable');
  });

  it('ledger table uses standard row density class under compact shell', async () => {
    seedShellAuth('owner');
    render(
      <MemoryRouter
        initialEntries={[
          '/app/benchmarks?dateFrom=2026-04-01&dateTo=2026-06-30&platformId=meta&platformId=google&platformId=email&commerceSourceId=shopify&commerceSourceId=stripe',
        ]}
      >
        <Routes>
          <Route path="/app" element={<AuthenticatedAppShell />}>
            <Route path="benchmarks" element={<BenchmarksPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());
    const row = document.querySelector('table tbody tr');
    expect(row?.className).toMatch(/rowStandard/);
    expect(document.querySelector('[data-authenticated-app-shell]')?.getAttribute('data-density')).toBe(
      'enterprise-compact',
    );
  });
});
