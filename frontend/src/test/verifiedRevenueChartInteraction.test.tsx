import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { VerifiedRevenueChart } from '../components/commandCenter/VerifiedRevenueChart/VerifiedRevenueChart';
import {
  buildReferenceTrendPoints,
  buildVerifiedRevenueChartGeometry,
  VERIFIED_REVENUE_CHART_HEIGHT,
  VERIFIED_REVENUE_CHART_WIDTH,
} from '../components/commandCenter/VerifiedRevenueChart/verifiedRevenueChartGeometry';

function mockLayoutRect(element: Element, rect: DOMRectInit): void {
  element.getBoundingClientRect = () =>
    ({
      x: rect.x ?? rect.left ?? 0,
      y: rect.y ?? rect.top ?? 0,
      width: rect.width ?? 0,
      height: rect.height ?? 0,
      top: rect.top ?? 0,
      left: rect.left ?? 0,
      right: (rect.left ?? 0) + (rect.width ?? 0),
      bottom: (rect.top ?? 0) + (rect.height ?? 0),
      toJSON: () => ({}),
    }) as DOMRect;
}

describe('VerifiedRevenueChart interaction', () => {
  it('shows proof-bearing tooltip for hovered snapshot point', () => {
    const points = buildReferenceTrendPoints().map((point) =>
      point.date === '2026-06-18' ? { ...point, verifiedRevenueMinor: 1_842_000n } : point,
    );

    const { container } = render(
      <MemoryRouter>
        <VerifiedRevenueChart points={points} />
      </MemoryRouter>,
    );
    const wrap = container.querySelector('[data-verified-revenue-chart]');
    const svg = container.querySelector('svg');
    const hitArea = container.querySelector('[data-plot-hit-area]');
    expect(wrap && svg && hitArea).toBeTruthy();

    mockLayoutRect(wrap!, { left: 0, top: 0, width: VERIFIED_REVENUE_CHART_WIDTH, height: VERIFIED_REVENUE_CHART_HEIGHT });
    mockLayoutRect(svg!, { left: 0, top: 0, width: VERIFIED_REVENUE_CHART_WIDTH, height: VERIFIED_REVENUE_CHART_HEIGHT });

    const geometry = buildVerifiedRevenueChartGeometry(points);
    const june18Index = geometry.coords.findIndex((coord) => coord.point.date === '2026-06-18');
    const clientX = geometry.coords[june18Index]!.x;

    fireEvent.pointerMove(hitArea!, { clientX, clientY: 140 });

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('Jun 18');
    expect(tooltip).toHaveTextContent('$18,420.00');
    expect(tooltip).not.toHaveTextContent('Source: verified_revenue_minor');
    expect(tooltip).not.toHaveTextContent('00:00');
    expect(tooltip?.parentElement?.querySelector('[style*="left"]')).toBeTruthy();
  });

  it('keeps hover mapping accurate when the plot region is taller than the viewBox aspect', () => {
    const points = buildReferenceTrendPoints().map((point) =>
      point.date === '2026-06-18' ? { ...point, verifiedRevenueMinor: 1_842_000n } : point,
    );

    const { container } = render(
      <MemoryRouter>
        <VerifiedRevenueChart points={points} />
      </MemoryRouter>,
    );
    const wrap = container.querySelector('[data-verified-revenue-chart]');
    const svg = container.querySelector('svg');
    const hitArea = container.querySelector('[data-plot-hit-area]');
    expect(wrap && svg && hitArea).toBeTruthy();

    mockLayoutRect(wrap!, {
      left: 0,
      top: 0,
      width: VERIFIED_REVENUE_CHART_WIDTH,
      height: VERIFIED_REVENUE_CHART_HEIGHT + 120,
    });
    mockLayoutRect(svg!, {
      left: 0,
      top: 0,
      width: VERIFIED_REVENUE_CHART_WIDTH,
      height: VERIFIED_REVENUE_CHART_HEIGHT + 120,
    });

    const geometry = buildVerifiedRevenueChartGeometry(points);
    const june18Index = geometry.coords.findIndex((coord) => coord.point.date === '2026-06-18');
    const clientX = geometry.coords[june18Index]!.x;

    fireEvent.pointerMove(hitArea!, { clientX, clientY: 300 });

    expect(screen.getByRole('tooltip')).toHaveTextContent('$18,420.00');
  });
});
