import { describe, expect, it } from 'vitest';
import {
  TREND_CHART_REFERENCE_DAY_COUNT,
  TREND_CHART_REFERENCE_END,
  TREND_CHART_REFERENCE_START,
  analyzeReferenceTrendDynamics,
  buildDailyVerifiedRevenueMinor,
  interpolateVerifiedRevenueTrendMinor,
  buildFixedIntervalAxisLabelDates,
  buildFiveDayAxisLabelDates,
  buildTrendAxisLabelDates,
  buildReferenceTrendPoints,
  buildVerifiedRevenueAxisTickMinors,
  buildVerifiedRevenueChartGeometry,
  findNearestPointIndexFromPlotX,
  formatTrendAxisDateLabel,
  formatTrendTooltipLabel,
  formatTrendTooltipLabelLegacy,
  formatVerifiedRevenueAxisLabel,
  getVerifiedRevenuePlotAreaSize,
  getVerifiedRevenuePlotUtilization,
  referenceTrendVerticalSpan,
  maxDailyRippleDeviationMinors,
  maxMacroDailyDeltaInReferenceDateRange,
  maxMacroDailyDeltaMinors,
  VERIFIED_REVENUE_LATE_JUNE_MAX_MACRO_DAILY_DELTA_MINOR,
  VERIFIED_REVENUE_MAX_MACRO_DAILY_DELTA_MINOR,
  VERIFIED_REVENUE_CHART_AXIS,
  VERIFIED_REVENUE_CHART_PAD,
  VERIFIED_REVENUE_CHART_PLOT_HEIGHT,
  VERIFIED_REVENUE_CHART_HEIGHT,
  VERIFIED_REVENUE_CHART_MIN_PLOT_UTILIZATION,
  VERIFIED_REVENUE_CHART_PRESERVE_ASPECT_RATIO,
  VERIFIED_REVENUE_CHART_WIDTH,
  VERIFIED_REVENUE_GRID_CELL,
  VERIFIED_REVENUE_GRID_X_INTERVALS,
  VERIFIED_REVENUE_GRID_Y_INTERVALS,
  VERIFIED_REVENUE_X_LABEL_MIN_SPACING,
  VERIFIED_REVENUE_X_LABEL_MIN_GAP,
  resolveTrendAxisLabelExtents,
  VERIFIED_REVENUE_DAILY_RIPPLE_MAX_MINOR,
  buildGridAlignedAxisLabelDates,
  createVerifiedRevenueChartScales,
  getVerifiedRevenueAxisGrid,
  getVerifiedRevenueChartViewportMapping,
  mapClientXToViewBoxX,
  mapViewBoxPointToClient,
  resolveVerifiedRevenueYDomain,
} from '../components/commandCenter/VerifiedRevenueChart/verifiedRevenueChartGeometry';
import {
  B210_UNAVAILABLE_SNAPSHOT_DATE,
  buildB210RevenueSnapshotSeries,
} from '../commandCenter/revenueSnapshotFixtures';

describe('verifiedRevenueChartGeometry', () => {
  it('exposes seven y-axis ticks from 10K through 40K at $5k steps', () => {
    const ticks = buildVerifiedRevenueAxisTickMinors();
    expect(ticks).toHaveLength(7);
    expect(ticks.map(formatVerifiedRevenueAxisLabel)).toEqual([
      '10K',
      '15K',
      '20K',
      '25K',
      '30K',
      '35K',
      '40K',
    ]);
  });

  it('builds reference trend window with one point per calendar day', () => {
    const points = buildReferenceTrendPoints();
    expect(points).toHaveLength(TREND_CHART_REFERENCE_DAY_COUNT);
    expect(points[0]?.date).toBe(TREND_CHART_REFERENCE_START);
    expect(points[points.length - 1]?.date).toBe(TREND_CHART_REFERENCE_END);
  });

  it('builds five-day candidate ticks for the reference window', () => {
    const labels = buildFixedIntervalAxisLabelDates(
      TREND_CHART_REFERENCE_START,
      TREND_CHART_REFERENCE_END,
      5,
    );
    expect(labels).toEqual([
      '2026-05-19',
      '2026-05-24',
      '2026-05-29',
      '2026-06-03',
      '2026-06-08',
      '2026-06-13',
      '2026-06-18',
      '2026-06-23',
      '2026-06-28',
      '2026-07-03',
      '2026-07-08',
      '2026-07-13',
      '2026-07-18',
    ]);
    const refPoints = buildReferenceTrendPoints();
    expect(
      labels.map((date) => formatTrendAxisDateLabel(refPoints.find((p) => p.date === date)!)),
    ).toEqual([
      'May 19',
      'May 24',
      'May 29',
      'Jun 3',
      'Jun 8',
      'Jun 13',
      'Jun 18',
      'Jun 23',
      'Jun 28',
      'Jul 3',
      'Jul 8',
      'Jul 13',
      'Jul 18',
    ]);
    expect(buildFiveDayAxisLabelDates(TREND_CHART_REFERENCE_START, TREND_CHART_REFERENCE_END)).toEqual(labels);
  });

  it('places x-axis labels on the shared grid at equal time ratios', () => {
    const { plotW } = getVerifiedRevenuePlotAreaSize();
    const labels = buildTrendAxisLabelDates(TREND_CHART_REFERENCE_START, TREND_CHART_REFERENCE_END, plotW);
    const refPoints = buildReferenceTrendPoints();
    expect(labels).toHaveLength(VERIFIED_REVENUE_GRID_X_INTERVALS + 1);
    expect(
      labels.map((date) => formatTrendAxisDateLabel(refPoints.find((p) => p.date === date)!)),
    ).toEqual([
      'May 19',
      'May 24',
      'May 29',
      'Jun 3',
      'Jun 8',
      'Jun 13',
      'Jun 18',
      'Jun 23',
      'Jun 28',
      'Jul 3',
      'Jul 8',
      'Jul 13',
      'Jul 18',
    ]);
    expect(buildGridAlignedAxisLabelDates(TREND_CHART_REFERENCE_START, TREND_CHART_REFERENCE_END)).toEqual(labels);

    const rollingLabels = buildTrendAxisLabelDates('2026-05-02', '2026-07-01', plotW);
    expect(rollingLabels).toHaveLength(VERIFIED_REVENUE_GRID_X_INTERVALS + 1);
    expect(rollingLabels[0]).toBe('2026-05-02');
    expect(rollingLabels[rollingLabels.length - 1]).toBe('2026-07-01');
  });

  it('fills the 10K–40K vertical axis span for reference data', () => {
    const span = referenceTrendVerticalSpan();
    expect(span.minRatio).toBeLessThan(0.2);
    expect(span.maxRatio).toBeGreaterThan(0.75);
  });

  it('anchors x-axis labels on the shared grid with Y-axis-matched single-line spacing', () => {
    const geometry = buildVerifiedRevenueChartGeometry(buildReferenceTrendPoints());
    const grid = getVerifiedRevenueAxisGrid();
    expect(geometry.xLabels[0]?.textAnchor).toBe('start');
    expect(geometry.xLabels[1]?.textAnchor).toBe('start');
    expect(geometry.xLabels[2]?.textAnchor).toBe('start');
    expect(geometry.xLabels[geometry.xLabels.length - 1]?.textAnchor).toBe('start');
    expect(geometry.xLabels[geometry.xLabels.length - 1]?.label).toMatch(/^Jul/);

    expect(geometry.xLabels).toHaveLength(grid.xLabelCount);
    expect(geometry.yTicks.length).toBeGreaterThanOrEqual(grid.yTickCount);
    expect(VERIFIED_REVENUE_X_LABEL_MIN_SPACING).toBe(VERIFIED_REVENUE_GRID_CELL);

    const labelRows = new Set(geometry.xLabels.map((label) => label.labelY));
    expect(labelRows.size).toBe(1);

    for (let index = 1; index < geometry.xLabels.length; index += 1) {
      const spacing = geometry.xLabels[index]!.x - geometry.xLabels[index - 1]!.x;
      expect(spacing).toBeCloseTo(VERIFIED_REVENUE_GRID_CELL, 5);
    }

    for (let index = 1; index < geometry.xLabels.length; index += 1) {
      const previous = resolveTrendAxisLabelExtents(geometry.xLabels[index - 1]!);
      const current = resolveTrendAxisLabelExtents(geometry.xLabels[index]!);
      expect(current.left - previous.right).toBeGreaterThanOrEqual(VERIFIED_REVENUE_X_LABEL_MIN_GAP);
    }

    for (let index = 1; index < geometry.yTicks.length; index += 1) {
      const spacing = geometry.yTicks[index - 1]!.y - geometry.yTicks[index]!.y;
      expect(spacing).toBeGreaterThan(0);
    }
  });

  it('governs both axes with one shared grid cell size', () => {
    const grid = getVerifiedRevenueAxisGrid();
    expect(grid.cell).toBe(VERIFIED_REVENUE_GRID_CELL);
    expect(grid.xIntervals).toBe(VERIFIED_REVENUE_GRID_X_INTERVALS);
    expect(grid.yIntervals).toBe(VERIFIED_REVENUE_GRID_Y_INTERVALS);
    expect(grid.plotW).toBe(VERIFIED_REVENUE_GRID_CELL * VERIFIED_REVENUE_GRID_X_INTERVALS);
    expect(grid.plotH).toBe(VERIFIED_REVENUE_GRID_CELL * VERIFIED_REVENUE_GRID_Y_INTERVALS);
    expect(grid.plotW / grid.xIntervals).toBe(grid.plotH / grid.yIntervals);
  });

  it('uses D3 scaleUtc + scaleLinear as the single axis authority', () => {
    const { yMinMinor, yMaxMinor } = resolveVerifiedRevenueYDomain(buildReferenceTrendPoints());
    const scales = createVerifiedRevenueChartScales(
      buildReferenceTrendPoints()[0]!.windowStartAt,
      buildReferenceTrendPoints().at(-1)!.windowEndAt,
      yMinMinor,
      yMaxMinor,
    );
    expect(scales.plotW).toBe(VERIFIED_REVENUE_GRID_CELL * VERIFIED_REVENUE_GRID_X_INTERVALS);
    expect(scales.plotH).toBe(VERIFIED_REVENUE_GRID_CELL * VERIFIED_REVENUE_GRID_Y_INTERVALS);
    expect(scales.x.range()).toEqual([scales.plotLeft, scales.plotRight]);
    expect(scales.y.range()).toEqual([scales.plotBottom, scales.plotTop]);

    const yZero = scales.y(Number(0n));
    const yOneM = scales.y(Number(1_000_000n));
    const yTwoM = scales.y(Number(2_000_000n));
    const yFourM = scales.y(Number(4_000_000n));
    expect(yZero! - yOneM!).toBeGreaterThan(0);
    expect(yOneM! - yTwoM!).toBeGreaterThan(0);
    expect(yZero! - yFourM!).toBeCloseTo(VERIFIED_REVENUE_GRID_CELL * VERIFIED_REVENUE_GRID_Y_INTERVALS, 0);

    const geometry = buildVerifiedRevenueChartGeometry(buildReferenceTrendPoints());
    expect(geometry.lineSegments.length).toBeGreaterThanOrEqual(2);
    expect(geometry.lineSegments.join('')).toMatch(/^M[\d.-]+,[\d.-]+/);
    expect(geometry.lineSegments.join('')).toContain('L');
    expect(geometry.gapMarkers.some((marker) => marker.point.date === B210_UNAVAILABLE_SNAPSHOT_DATE)).toBe(
      true,
    );
    expect(geometry.areaSegments[0]).toMatch(/Z$/i);
  });

  it('renders polyline segments without curve commands and breaks across missing snapshots', () => {
    const geometry = buildVerifiedRevenueChartGeometry(buildB210RevenueSnapshotSeries());
    expect(geometry.coords).toHaveLength(TREND_CHART_REFERENCE_DAY_COUNT);
    expect(geometry.lineSegments.length).toBeGreaterThan(1);
    for (const segment of geometry.lineSegments) {
      expect(segment).not.toMatch(/[CQSTcqst]/);
    }
    expect(geometry.yTicks.length).toBeGreaterThanOrEqual(VERIFIED_REVENUE_GRID_Y_INTERVALS + 1);
    expect(geometry.xLabels).toHaveLength(VERIFIED_REVENUE_GRID_X_INTERVALS + 1);
  });

  it('maximizes plot area within the fixed viewBox', () => {
    const utilization = getVerifiedRevenuePlotUtilization();
    expect(utilization).toBeGreaterThanOrEqual(VERIFIED_REVENUE_CHART_MIN_PLOT_UTILIZATION);
  });

  it('formats tooltip copy with cents proof and window range', () => {
    const point = buildReferenceTrendPoints().find((p) => p.date === '2026-06-18')!;
    const tooltip = formatTrendTooltipLabel(point);
    expect(tooltip.dateLabel).toMatch(/Jun 18/);
    expect(tooltip.primaryValue).toMatch(/^\$[\d,]+\.\d{2}$/);
    expect(tooltip.sourceProof).toBe(`Source: verified_revenue_minor (${point.verifiedRevenueMinor.toString()})`);
    expect(tooltip.windowRange).toMatch(/Jun 18/);
    expect(formatTrendTooltipLabelLegacy('2026-06-18', 1_842_000n)).toBe('June 18 • $18,420');
  });

  it('renders all thirteen grid-aligned X labels inside the axis gutter', () => {
    const geometry = buildVerifiedRevenueChartGeometry(buildReferenceTrendPoints());
    expect(geometry.xLabels).toHaveLength(VERIFIED_REVENUE_GRID_X_INTERVALS + 1);
    for (const [index, label] of geometry.xLabels.entries()) {
      expect(label.x).toBeCloseTo(
        VERIFIED_REVENUE_CHART_PAD.left + index * VERIFIED_REVENUE_GRID_CELL,
        5,
      );
      expect(label.labelY).toBe(VERIFIED_REVENUE_CHART_AXIS.xLabelY);
      expect(label.labelY).toBeGreaterThan(VERIFIED_REVENUE_CHART_PAD.top + VERIFIED_REVENUE_CHART_PLOT_HEIGHT);
      expect(label.labelY + VERIFIED_REVENUE_CHART_AXIS.xLabelFontSize).toBeLessThanOrEqual(
        VERIFIED_REVENUE_CHART_HEIGHT,
      );
      expect(label.rotation).toBe(0);
      const extents = resolveTrendAxisLabelExtents(label);
      expect(extents.left).toBeGreaterThanOrEqual(0);
      expect(extents.right).toBeLessThanOrEqual(VERIFIED_REVENUE_CHART_WIDTH);
    }
  });

  it('finds nearest daily point from plot x position', () => {
    const geometry = buildVerifiedRevenueChartGeometry(buildReferenceTrendPoints());
    const june18Index = geometry.coords.findIndex((coord) => coord.point.date === '2026-06-18');
    expect(june18Index).toBeGreaterThan(-1);
    const june18X = geometry.coords[june18Index]!.x;
    expect(findNearestPointIndexFromPlotX(june18X, geometry.coords)).toBe(june18Index);
    expect(findNearestPointIndexFromPlotX(june18X + 0.5, geometry.coords)).toBe(june18Index);
  });

  it('models uneven B2B growth with plateaus, dips, and net upward trend', () => {
    const dynamics = analyzeReferenceTrendDynamics();
    expect(dynamics.netGrowthMinor).toBeGreaterThan(2_000_000n);
    expect(dynamics.downDays).toBeGreaterThanOrEqual(8);
    expect(dynamics.plateauRuns).toBeGreaterThanOrEqual(2);
    expect(dynamics.hasMacroDip).toBe(true);
  });

  it('keeps late-June through early-July growth paced without sharp jumps', () => {
    const lateJuneDelta = maxMacroDailyDeltaInReferenceDateRange('2026-06-26', '2026-07-01');
    expect(lateJuneDelta).toBeLessThanOrEqual(VERIFIED_REVENUE_LATE_JUNE_MAX_MACRO_DAILY_DELTA_MINOR);
    expect(maxMacroDailyDeltaMinors(TREND_CHART_REFERENCE_DAY_COUNT)).toBeLessThanOrEqual(
      VERIFIED_REVENUE_MAX_MACRO_DAILY_DELTA_MINOR,
    );
  });

  it('keeps daily ripple subtle with angular day-to-day vertices', () => {
    const values = Array.from({ length: TREND_CHART_REFERENCE_DAY_COUNT }, (_, index) =>
      buildDailyVerifiedRevenueMinor(index),
    );
    const deltas = values.slice(1).map((value, index) => {
      const previous = values[index]!;
      return value > previous ? value - previous : previous - value;
    });
    expect(deltas.some((delta) => delta > 0n)).toBe(true);
    expect(maxDailyRippleDeviationMinors(TREND_CHART_REFERENCE_DAY_COUNT)).toBeLessThanOrEqual(
      VERIFIED_REVENUE_DAILY_RIPPLE_MAX_MINOR,
    );
    expect(values[0]!).toBeGreaterThanOrEqual(1_000_000n);
    expect(values[values.length - 1]!).toBeLessThanOrEqual(3_950_000n);
  });

  it('maps viewport coordinates for top-anchored uniform scaling', () => {
    expect(VERIFIED_REVENUE_CHART_PRESERVE_ASPECT_RATIO).toBe('xMinYMin meet');

    const tallMapping = getVerifiedRevenueChartViewportMapping(
      VERIFIED_REVENUE_CHART_WIDTH,
      VERIFIED_REVENUE_CHART_HEIGHT + 120,
    );
    expect(tallMapping.scale).toBeCloseTo(1, 5);
    expect(tallMapping.offsetY).toBeCloseTo(0, 5);
    expect(tallMapping.renderedHeight).toBeCloseTo(VERIFIED_REVENUE_CHART_HEIGHT, 5);

    const wideScale = 1.5;
    const wideMapping = getVerifiedRevenueChartViewportMapping(
      VERIFIED_REVENUE_CHART_WIDTH * wideScale,
      VERIFIED_REVENUE_CHART_HEIGHT * wideScale,
    );
    expect(wideMapping.scale).toBeCloseTo(wideScale, 5);
    expect(wideMapping.offsetY).toBeCloseTo(0, 5);
    expect(wideMapping.renderedHeight).toBeCloseTo(VERIFIED_REVENUE_CHART_HEIGHT * wideScale, 5);

    const svgRect = {
      left: 10,
      top: 20,
      width: VERIFIED_REVENUE_CHART_WIDTH,
      height: VERIFIED_REVENUE_CHART_HEIGHT + 120,
    } as DOMRect;
    expect(mapClientXToViewBoxX(10, svgRect)).toBeCloseTo(0, 5);
    const mapped = mapViewBoxPointToClient(VERIFIED_REVENUE_CHART_WIDTH / 2, VERIFIED_REVENUE_CHART_HEIGHT / 2, svgRect);
    expect(mapped?.clientX).toBeCloseTo(10 + VERIFIED_REVENUE_CHART_WIDTH / 2, 5);
    expect(mapped?.clientY).toBeCloseTo(20 + VERIFIED_REVENUE_CHART_HEIGHT / 2, 5);
  });
});
