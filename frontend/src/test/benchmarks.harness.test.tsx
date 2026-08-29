import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { BenchmarksPage } from '../components/benchmarks/BenchmarksPage/BenchmarksPage';
import { BenchmarkCell } from '../components/ledger/BenchmarkCell/BenchmarkCell';
import { BENCHMARKS_COPY } from '../benchmarks/copy';
import { resetDefaultBenchmarksClient } from '../benchmarks/benchmarksClient';
import { resetDefaultBenchmarkDetailClient } from '../benchmarks/benchmarkDetailClient';
import { seedShellAuth } from './level9.helpers';

function renderBenchmarks(
  initialPath = '/app/benchmarks?dateFrom=2026-04-01&dateTo=2026-06-30&pageSize=50',
) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/app/benchmarks" element={<BenchmarksPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Benchmark Intelligence CRHAID 1 harness', () => {
  beforeEach(() => {
    seedShellAuth('owner');
    resetDefaultBenchmarksClient();
    resetDefaultBenchmarkDetailClient();
  });

  it('renders exactly eight mandatory data columns', async () => {
    renderBenchmarks();
    await waitFor(() => expect(document.querySelector('[data-benchmarks-results]')).toBeInTheDocument());

    const headers = screen.getAllByRole('columnheader').map((node) => node.textContent?.trim());
    expect(headers).toEqual([
      'Benchmark name',
      'Raw benchmark',
      'Decision-safe benchmark',
      'Evidence class',
      'Coverage class',
      'Suppression reason',
      'Comparable to previous',
      'Actionability',
    ]);
  });

  it('renders segment rows with CRHAID evidence badges and coverage vocabulary', async () => {
    renderBenchmarks();
    await waitFor(() => expect(screen.getByText('Meta Ads × Paid Social')).toBeInTheDocument());

    expect(document.querySelector('[data-evidence-class-badge="live_empirical"]')).toBeInTheDocument();
    expect(document.querySelector('[data-coverage-class-badge="exact"]')).toBeInTheDocument();
    expect(document.querySelector('[data-coverage-class-badge="broad"]')).toBeInTheDocument();
    expect(document.querySelector('[data-actionability-pill="simulate"]')).toBeInTheDocument();
  });

  it('shows N/A with unavailable copy only as hover tooltip for suppressed segments', async () => {
    renderBenchmarks();
    await waitFor(() => expect(screen.getByText('TikTok Ads × Snapchat Swipe')).toBeInTheDocument());

    expect(screen.queryByText(BENCHMARKS_COPY.table.unavailableSegmentCopy)).not.toBeInTheDocument();
    const naValues = document.querySelectorAll('[data-benchmark-na-value]');
    expect(naValues.length).toBeGreaterThan(0);
    naValues.forEach((node) => {
      expect(node).toHaveAttribute('title', BENCHMARKS_COPY.table.unavailableSegmentCopy);
    });
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0);
    expect(document.querySelector('[data-benchmark-suppression-code="low_k"]')).toBeInTheDocument();
  });

  it('shows historical prior disclaimer and estimator transition badge', async () => {
    renderBenchmarks();
    await waitFor(() =>
      expect(screen.getByText('Meta Ads × Paid Search × US')).toBeInTheDocument(),
    );

    expect(screen.getByText(BENCHMARKS_COPY.table.historicalPriorDisclaimer)).toBeInTheDocument();
    expect(document.querySelector('[data-estimator-transition-badge]')).toBeInTheDocument();
    expect(
      document.querySelector('[data-actionability-pill="observe_only_until_stable"]'),
    ).toBeInTheDocument();
  });

  it('opens benchmark source detail drawer from row activation', async () => {
    const user = userEvent.setup();
    renderBenchmarks();
    await waitFor(() => expect(screen.getByText('Meta Ads × Paid Social')).toBeInTheDocument());
    await user.click(screen.getByText('Meta Ads × Paid Social'));
    await waitFor(() =>
      expect(document.querySelector('[data-benchmark-source-detail-drawer]')).toBeInTheDocument(),
    );
    expect(screen.getByText('Related TrustEnvelope')).toBeInTheDocument();
  });

  it('renders evidence badges without bracket wrappers', async () => {
    renderBenchmarks();
    await waitFor(() => expect(screen.getByText('Meta Ads × Paid Social')).toBeInTheDocument());

    const badges = document.querySelectorAll('[data-evidence-class-badge]');
    expect(badges.length).toBeGreaterThan(0);
    badges.forEach((badge) => {
      expect(badge.textContent).not.toMatch(/^\[/);
      expect(badge.textContent).not.toMatch(/\]$/);
    });
  });

  it('BenchmarkCell uses CRHAID semantic badges for available benchmark', () => {
    render(
      <BenchmarkCell
        benchmark={{
          status: 'available',
          evidenceClass: 'live_empirical',
          coverageClass: 'exact',
          rawBenchmark: '1.94%',
          decisionSafeBenchmark: '1.71%',
        }}
      />,
    );
    expect(screen.getByText('Live Skeldir Empirical')).toBeInTheDocument();
    expect(screen.getByText('Exact')).toBeInTheDocument();
    expect(screen.getByText(/Raw: 1.94%/)).toBeInTheDocument();
    expect(screen.getByText(/Decision-safe: 1.71%/)).toBeInTheDocument();
  });
});
