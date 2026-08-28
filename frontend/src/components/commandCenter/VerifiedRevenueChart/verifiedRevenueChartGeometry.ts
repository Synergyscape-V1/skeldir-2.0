import {
  VERIFIED_REVENUE_AXIS_MIN_MINOR,
  VERIFIED_REVENUE_AXIS_MAX_MINOR,
  buildDailyVerifiedRevenueMinor,
  interpolateVerifiedRevenueTrendMinor,
} from '../../../commandCenter/trendSyntheticData';

export {
  VERIFIED_REVENUE_AXIS_MIN_MINOR,
  VERIFIED_REVENUE_AXIS_MAX_MINOR,
  buildDailyVerifiedRevenueMinor,
  interpolateVerifiedRevenueTrendMinor,
};

import { bisector } from 'd3-array';
import { scaleLinear, scaleUtc, type ScaleLinear, type ScaleTime } from 'd3-scale';
import { area, curveLinear, line } from 'd3-shape';
import { formatMoneyMinorDisplay, formatMoneyMinorDisplayWithCents } from '../../../lib/money';
import type { TrendPoint } from '../../../commandCenter/types';
import { buildB210RevenueSnapshotSeries } from '../../../commandCenter/revenueSnapshotFixtures';

/** $5k tick step in USD minor units (cents). */
export const VERIFIED_REVENUE_AXIS_STEP_MINOR = 500_000n;

/** Reference trend window — one daily point per calendar day (inclusive). */
export const TREND_CHART_REFERENCE_START = '2026-05-19';
export const TREND_CHART_REFERENCE_END = '2026-07-18';
export const TREND_CHART_REFERENCE_DAY_COUNT = 61;
export const TREND_AXIS_LABEL_INTERVAL_DAYS = 5;

/**
 * Shared axis grid — one cell size governs both axes so Y value ticks and X date
 * labels read as matched-interval scales (enterprise line-chart standard).
 * Y: 7 ticks (10K–40K at $5k) → 6 equal intervals.
 * X: 13 date labels (12 intervals, every 5 days) — cell width sized for readable type.
 */
export const VERIFIED_REVENUE_GRID_Y_INTERVALS = 6;
export const VERIFIED_REVENUE_GRID_X_INTERVALS = 12;
export const VERIFIED_REVENUE_GRID_CELL = 44;

/** Center-to-center spacing for axis labels equals the shared grid cell. */
export const VERIFIED_REVENUE_X_LABEL_MIN_SPACING = VERIFIED_REVENUE_GRID_CELL;

/** Minimum clear gap between consecutive X-axis label bounding boxes. */
export const VERIFIED_REVENUE_X_LABEL_MIN_GAP = 6;

/** Plot area is an exact grid of square cells (no independent axis spacing). */
export const VERIFIED_REVENUE_CHART_PLOT_WIDTH =
  VERIFIED_REVENUE_GRID_CELL * VERIFIED_REVENUE_GRID_X_INTERVALS;
export const VERIFIED_REVENUE_CHART_PLOT_HEIGHT =
  VERIFIED_REVENUE_GRID_CELL * VERIFIED_REVENUE_GRID_Y_INTERVALS;

/** X-axis label typography — single horizontal row matching the Y-axis (var(--sk-space-2), shared grid). */
export const VERIFIED_REVENUE_CHART_X_LABEL_FONT_SIZE = 8;
export const VERIFIED_REVENUE_CHART_X_LABEL_OFFSET = 6;

/** Bottom gutter reserved for one row of X-axis labels (kept inside the viewBox). */
export const VERIFIED_REVENUE_CHART_X_AXIS_GUTTER =
  VERIFIED_REVENUE_CHART_X_LABEL_OFFSET + VERIFIED_REVENUE_CHART_X_LABEL_FONT_SIZE + 6;

/** Label gutters — sized so plot remains an exact shared-grid rectangle. */
export const VERIFIED_REVENUE_CHART_PAD = {
  top: 6,
  right: 32,
  bottom: 16 + VERIFIED_REVENUE_CHART_X_AXIS_GUTTER,
  left: 28,
} as const;

/** ViewBox derived from shared grid + gutters (uniform scale via preserveAspectRatio meet). */
export const VERIFIED_REVENUE_CHART_WIDTH =
  VERIFIED_REVENUE_CHART_PAD.left + VERIFIED_REVENUE_CHART_PLOT_WIDTH + VERIFIED_REVENUE_CHART_PAD.right;
export const VERIFIED_REVENUE_CHART_HEIGHT =
  VERIFIED_REVENUE_CHART_PAD.top + VERIFIED_REVENUE_CHART_PLOT_HEIGHT + VERIFIED_REVENUE_CHART_PAD.bottom;

/** Top-anchored uniform scale — plot begins directly under header/legend without vertical dead space. */
export const VERIFIED_REVENUE_CHART_PRESERVE_ASPECT_RATIO = 'xMinYMin meet' as const;

export interface VerifiedRevenueChartViewportMapping {
  scale: number;
  offsetX: number;
  offsetY: number;
  renderedWidth: number;
  renderedHeight: number;
}

export function getVerifiedRevenueChartViewportMapping(
  viewportWidth: number,
  viewportHeight: number,
): VerifiedRevenueChartViewportMapping {
  if (viewportWidth <= 0 || viewportHeight <= 0) {
    return { scale: 1, offsetX: 0, offsetY: 0, renderedWidth: 0, renderedHeight: 0 };
  }

  const scale = Math.min(
    viewportWidth / VERIFIED_REVENUE_CHART_WIDTH,
    viewportHeight / VERIFIED_REVENUE_CHART_HEIGHT,
  );
  const renderedWidth = VERIFIED_REVENUE_CHART_WIDTH * scale;
  const renderedHeight = VERIFIED_REVENUE_CHART_HEIGHT * scale;

  return {
    scale,
    offsetX: 0,
    offsetY: 0,
    renderedWidth,
    renderedHeight,
  };
}

export function mapClientXToViewBoxX(clientX: number, svgRect: DOMRect): number | null {
  if (svgRect.width <= 0 || svgRect.height <= 0) return null;
  const { scale, offsetX } = getVerifiedRevenueChartViewportMapping(svgRect.width, svgRect.height);
  return (clientX - svgRect.left - offsetX) / scale;
}

export function mapViewBoxPointToClient(
  viewBoxX: number,
  viewBoxY: number,
  svgRect: DOMRect,
): { clientX: number; clientY: number } | null {
  if (svgRect.width <= 0 || svgRect.height <= 0) return null;
  const { scale, offsetX, offsetY } = getVerifiedRevenueChartViewportMapping(svgRect.width, svgRect.height);
  return {
    clientX: svgRect.left + offsetX + viewBoxX * scale,
    clientY: svgRect.top + offsetY + viewBoxY * scale,
  };
}

/** Axis + stroke sizes in viewBox user units (scale with the SVG). */
export const VERIFIED_REVENUE_CHART_AXIS = {
  yLabelX: VERIFIED_REVENUE_CHART_PAD.left - 6,
  yLabelFontSize: 8,
  xLabelY:
    VERIFIED_REVENUE_CHART_PAD.top + VERIFIED_REVENUE_CHART_PLOT_HEIGHT + VERIFIED_REVENUE_CHART_X_LABEL_OFFSET,
  xLabelFontSize: VERIFIED_REVENUE_CHART_X_LABEL_FONT_SIZE,
  xLabelRotation: 0,
  lineStrokeWidth: 1.5,
  gridStrokeWidth: 1,
  activePointRadius: 4,
  /** Markers on the trend line at each labeled day. */
  labelMarkerRadius: 2.25,
  gapLabelFontSize: 7,
  /** Inset unavailable markers from the plot baseline so circles/labels are not clipped. */
  gapMarkerBaselineInset: 6,
  gapLabelOffset: 4,
} as const;

/**
 * Minimum plot-area-to-viewBox ratio for spatial utilization gate.
 * Derived from current grid + gutters (including X-axis label gutter) so the floor
 * tracks intentional bottom padding without penalizing rotated date labels.
 */
export const VERIFIED_REVENUE_CHART_MIN_PLOT_UTILIZATION =
  ((VERIFIED_REVENUE_CHART_PLOT_WIDTH * VERIFIED_REVENUE_CHART_PLOT_HEIGHT) /
    (VERIFIED_REVENUE_CHART_WIDTH * VERIFIED_REVENUE_CHART_HEIGHT)) *
  0.99;

/** Max deviation from macro trend baseline for gentle ripple texture. */
export const VERIFIED_REVENUE_DAILY_RIPPLE_MAX_MINOR = 90_000n;

/** Max macro day-over-day move across full reference window (~$1.1k/day). */
export const VERIFIED_REVENUE_MAX_MACRO_DAILY_DELTA_MINOR = 110_000n;

/** Max macro day-over-day move in late-June / early-July plateau band. */
export const VERIFIED_REVENUE_LATE_JUNE_MAX_MACRO_DAILY_DELTA_MINOR = 45_000n;

const MONTH_NAMES_FULL = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const;

export interface ChartPlotCoord {
  x: number;
  y: number;
  point: TrendPoint;
  index: number;
}

export interface ChartGapMarker {
  x: number;
  y: number;
  point: TrendPoint;
  index: number;
}

export function resolveGapLabelLayout(marker: ChartGapMarker): {
  labelY: number;
  textAnchor: 'start' | 'middle' | 'end';
  dx: number;
} {
  const plotLeft = VERIFIED_REVENUE_CHART_PAD.left;
  const plotRight = VERIFIED_REVENUE_CHART_PAD.left + VERIFIED_REVENUE_CHART_PLOT_WIDTH;
  const edgePad = 40;
  const labelY =
    marker.y -
    VERIFIED_REVENUE_CHART_AXIS.activePointRadius -
    VERIFIED_REVENUE_CHART_AXIS.gapLabelOffset;

  if (marker.x - plotLeft < edgePad) {
    return { labelY, textAnchor: 'start', dx: 2 };
  }
  if (plotRight - marker.x < edgePad) {
    return { labelY, textAnchor: 'end', dx: -2 };
  }
  return { labelY, textAnchor: 'middle', dx: 0 };
}

export interface ChartAxisLabel {
  x: number;
  label: string;
  date: string;
  textAnchor: 'start' | 'middle' | 'end';
  labelY: number;
  rotation: number;
}

export interface ChartYTick {
  y: number;
  label: string;
}

export function parseIsoDateUtc(isoDate: string): Date {
  const [year, month, day] = isoDate.split('-').map(Number);
  return new Date(Date.UTC(year!, month! - 1, day));
}

export function formatIsoDateUtc(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function addUtcDays(date: Date, days: number): Date {
  const next = new Date(date.getTime());
  next.setUTCDate(next.getUTCDate() + days);
  return next;
}

export function buildVerifiedRevenueAxisTickMinors(): bigint[] {
  const ticks: bigint[] = [];
  for (
    let value = VERIFIED_REVENUE_AXIS_MIN_MINOR;
    value <= VERIFIED_REVENUE_AXIS_MAX_MINOR;
    value += VERIFIED_REVENUE_AXIS_STEP_MINOR
  ) {
    ticks.push(value);
  }
  return ticks;
}

export function formatVerifiedRevenueAxisLabel(amountMinor: bigint): string {
  const major = amountMinor / 100n;
  const thousands = major / 1000n;
  return `${thousands}K`;
}

export function verifiedRevenueValueToPlotRatio(valueMinor: bigint): number {
  const min = Number(VERIFIED_REVENUE_AXIS_MIN_MINOR);
  const max = Number(VERIFIED_REVENUE_AXIS_MAX_MINOR);
  const span = Math.max(max - min, 1);
  const raw = (Number(valueMinor) - min) / span;
  return Math.min(1, Math.max(0, raw));
}

/** D3 margin convention — shared by both axis scales (see d3js.org/getting-started). */
export interface VerifiedRevenueChartMargins {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface VerifiedRevenueChartScales {
  x: ScaleTime<number, number>;
  y: ScaleLinear<number, number>;
  width: number;
  height: number;
  margin: VerifiedRevenueChartMargins;
  plotLeft: number;
  plotRight: number;
  plotTop: number;
  plotBottom: number;
  plotW: number;
  plotH: number;
}

/**
 * Single scale authority for both axes. X is UTC time, Y is linear minor-units.
 * Ranges share the same margin box so tick intervals read as one grid system.
 */
export function createVerifiedRevenueChartScales(
  minTimeIso: string,
  maxTimeIso: string,
  yMinMinor: bigint,
  yMaxMinor: bigint,
): VerifiedRevenueChartScales {
  const margin: VerifiedRevenueChartMargins = {
    top: VERIFIED_REVENUE_CHART_PAD.top,
    right: VERIFIED_REVENUE_CHART_PAD.right,
    bottom: VERIFIED_REVENUE_CHART_PAD.bottom,
    left: VERIFIED_REVENUE_CHART_PAD.left,
  };
  const width = VERIFIED_REVENUE_CHART_WIDTH;
  const height = VERIFIED_REVENUE_CHART_HEIGHT;
  const plotLeft = margin.left;
  const plotRight = width - margin.right;
  const plotTop = margin.top;
  const plotBottom = height - margin.bottom;

  const x = scaleUtc()
    .domain([parseIsoDateTimeUtc(minTimeIso), parseIsoDateTimeUtc(maxTimeIso)])
    .range([plotLeft, plotRight])
    .clamp(true);

  const y = scaleLinear()
    .domain([Number(yMinMinor), Number(yMaxMinor)])
    .range([plotBottom, plotTop])
    .clamp(true);

  return {
    x,
    y,
    width,
    height,
    margin,
    plotLeft,
    plotRight,
    plotTop,
    plotBottom,
    plotW: plotRight - plotLeft,
    plotH: plotBottom - plotTop,
  };
}

export function parseIsoDateTimeUtc(iso: string): Date {
  return new Date(iso);
}

export function trendPointPlotTime(point: TrendPoint): Date {
  const startMs = Date.parse(point.windowStartAt);
  const endMs = Date.parse(point.windowEndAt);
  return new Date((startMs + endMs) / 2);
}

export function formatTrendWindowRangeLabel(
  windowStartAt: string,
  windowEndAt: string,
  mode: 'axis' | 'tooltip' = 'tooltip',
): string {
  const start = new Date(windowStartAt);
  const end = new Date(windowEndAt);
  const monthShort = (date: Date) =>
    date.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
  const day = (date: Date) => date.getUTCDate();
  const hour = (date: Date) => String(date.getUTCHours()).padStart(2, '0');
  const minute = (date: Date) => String(date.getUTCMinutes()).padStart(2, '0');

  if (mode === 'axis') {
    const sameMonth = start.getUTCMonth() === end.getUTCMonth();
    if (sameMonth) {
      return `${monthShort(start)} ${day(start)}–${day(end)}`;
    }
    return `${monthShort(start)} ${day(start)} – ${monthShort(end)} ${day(end)}`;
  }

  return `${monthShort(start)} ${day(start)} ${hour(start)}:${minute(start)} – ${monthShort(end)} ${day(end)} ${hour(end)}:${minute(end)}`;
}

export function formatTrendAxisCompactLabel(point: TrendPoint): string {
  const start = new Date(point.windowStartAt);
  const monthShort = start.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
  return `${monthShort} ${start.getUTCDate()}`;
}

/** Conservative width estimate for var(--sk-space-2) body-strong axis labels (SVG user units). */
export function estimateTrendAxisLabelWidth(
  label: string,
  fontSize: number = VERIFIED_REVENUE_CHART_X_LABEL_FONT_SIZE,
): number {
  return label.length * fontSize * 0.62;
}

export function resolveTrendAxisLabelExtents(
  label: Pick<ChartAxisLabel, 'x' | 'label' | 'textAnchor'>,
): { left: number; right: number } {
  const width = estimateTrendAxisLabelWidth(label.label);
  switch (label.textAnchor) {
    case 'start':
      return { left: label.x, right: label.x + width };
    case 'end':
      return { left: label.x - width, right: label.x };
    default:
      return { left: label.x - width / 2, right: label.x + width / 2 };
  }
}

export function formatTrendAxisDateLabel(point: TrendPoint): string {
  return formatTrendAxisCompactLabel(point);
}

export function formatTrendTooltipLabel(
  point: TrendPoint,
  currencyCode = 'USD',
): {
  dateLabel: string;
  primaryValue: string;
  sourceProof: string;
  windowRange: string;
} {
  const primaryValue =
    point.status === 'unavailable'
      ? 'Data unavailable'
      : formatMoneyMinorDisplayWithCents(point.verifiedRevenueMinor, currencyCode);
  return {
    dateLabel: formatTrendAxisCompactLabel(point),
    primaryValue,
    sourceProof: `Source: ${point.sourceField} (${point.verifiedRevenueMinor.toString()})`,
    windowRange: formatTrendWindowRangeLabel(point.windowStartAt, point.windowEndAt, 'tooltip'),
  };
}

/** @deprecated Use formatTrendTooltipLabel(point) */
export function formatTrendTooltipLabelLegacy(
  dateIso: string,
  amountMinor: bigint,
  currencyCode = 'USD',
): string {
  const date = parseIsoDateUtc(dateIso);
  const month = MONTH_NAMES_FULL[date.getUTCMonth()];
  const day = date.getUTCDate();
  return `${month} ${day} • ${formatMoneyMinorDisplay(amountMinor, currencyCode)}`;
}

export function buildFixedIntervalAxisLabelDates(
  startIso: string,
  endIso: string,
  intervalDays: number,
): string[] {
  const labels: string[] = [];
  let current = parseIsoDateUtc(startIso);
  const end = parseIsoDateUtc(endIso);

  while (current.getTime() <= end.getTime()) {
    labels.push(formatIsoDateUtc(current));
    current = addUtcDays(current, intervalDays);
  }

  const last = labels[labels.length - 1];
  if (last && last !== endIso) {
    labels.push(endIso);
  }

  return labels;
}

/** @deprecated Use buildFixedIntervalAxisLabelDates or buildTrendAxisLabelDates. */
export function buildFiveDayAxisLabelDates(startIso: string, endIso: string): string[] {
  return buildFixedIntervalAxisLabelDates(startIso, endIso, TREND_AXIS_LABEL_INTERVAL_DAYS);
}

export function countUtcDaysInclusive(startIso: string, endIso: string): number {
  const start = parseIsoDateUtc(startIso);
  const end = parseIsoDateUtc(endIso);
  const spanMs = end.getTime() - start.getTime();
  return Math.max(0, Math.round(spanMs / (24 * 60 * 60 * 1000)));
}

/**
 * Dates at equal time ratios across the window — one label per shared-grid column,
 * including both endpoints. Always returns `xIntervals + 1` dates so label x-positions
 * land on exact grid columns (spacing === VERIFIED_REVENUE_GRID_CELL).
 */
export function buildGridAlignedAxisLabelDates(
  startIso: string,
  endIso: string,
  xIntervals: number = VERIFIED_REVENUE_GRID_X_INTERVALS,
): string[] {
  if (xIntervals < 1) return [startIso, endIso];

  const daySpan = countUtcDaysInclusive(startIso, endIso);
  const start = parseIsoDateUtc(startIso);
  const dates = Array.from({ length: xIntervals + 1 }, (_, interval) => {
    const dayOffset = daySpan <= 0 ? 0 : Math.round((interval / xIntervals) * daySpan);
    return formatIsoDateUtc(addUtcDays(start, dayOffset));
  });
  dates[0] = startIso;
  dates[dates.length - 1] = endIso;
  return dates;
}

/** X position for a shared-grid column — mirrors fixed Y tick spacing (VERIFIED_REVENUE_GRID_CELL). */
export function buildGridAlignedAxisLabelX(
  labelIndex: number,
  plotLeft: number = VERIFIED_REVENUE_CHART_PAD.left,
): number {
  return plotLeft + labelIndex * VERIFIED_REVENUE_GRID_CELL;
}

/** @deprecated Prefer buildGridAlignedAxisLabelDates — shared grid is the axis authority. */
export function computeTrendAxisLabelIntervalDays(
  startIso: string,
  endIso: string,
  _plotWidth: number,
): number {
  const daySpan = countUtcDaysInclusive(startIso, endIso);
  if (daySpan <= 0) return TREND_AXIS_LABEL_INTERVAL_DAYS;
  return Math.max(1, Math.round(daySpan / VERIFIED_REVENUE_GRID_X_INTERVALS));
}

/** @deprecated Prefer buildGridAlignedAxisLabelDates. */
export function resolveTrendAxisLabelDatesWithoutOverlap(
  labelDates: string[],
  _minDateIso: string,
  _maxDateIso: string,
  _plotLeft: number,
  _plotWidth: number,
): string[] {
  return labelDates;
}

export function buildTrendAxisLabelDates(
  startIso: string,
  endIso: string,
  _plotWidth: number = VERIFIED_REVENUE_CHART_PLOT_WIDTH,
  _plotLeft = VERIFIED_REVENUE_CHART_PAD.left,
): string[] {
  return buildGridAlignedAxisLabelDates(startIso, endIso, VERIFIED_REVENUE_GRID_X_INTERVALS);
}

export function getVerifiedRevenueAxisGrid(): {
  cell: number;
  xIntervals: number;
  yIntervals: number;
  plotW: number;
  plotH: number;
  xLabelCount: number;
  yTickCount: number;
} {
  return {
    cell: VERIFIED_REVENUE_GRID_CELL,
    xIntervals: VERIFIED_REVENUE_GRID_X_INTERVALS,
    yIntervals: VERIFIED_REVENUE_GRID_Y_INTERVALS,
    plotW: VERIFIED_REVENUE_CHART_PLOT_WIDTH,
    plotH: VERIFIED_REVENUE_CHART_PLOT_HEIGHT,
    xLabelCount: VERIFIED_REVENUE_GRID_X_INTERVALS + 1,
    yTickCount: VERIFIED_REVENUE_GRID_Y_INTERVALS + 1,
  };
}

export function dateToPlotX(
  point: TrendPoint,
  minTimeIso: string,
  maxTimeIso: string,
  yMinMinor: bigint,
  yMaxMinor: bigint,
  plotLeft: number,
  plotWidth: number,
): number {
  const { x } = createVerifiedRevenueChartScales(minTimeIso, maxTimeIso, yMinMinor, yMaxMinor);
  const scaled = x(trendPointPlotTime(point));
  if (scaled == null || Number.isNaN(scaled)) {
    const minMs = Date.parse(minTimeIso);
    const maxMs = Date.parse(maxTimeIso);
    const valueMs = trendPointPlotTime(point).getTime();
    const span = Math.max(maxMs - minMs, 1);
    return plotLeft + ((valueMs - minMs) / span) * plotWidth;
  }
  return scaled;
}

export function plotXToDateRatio(plotX: number, plotLeft: number, plotWidth: number): number {
  if (plotWidth <= 0) return 0;
  return Math.min(1, Math.max(0, (plotX - plotLeft) / plotWidth));
}

const plotCoordBisector = bisector<ChartPlotCoord, number>((coord) => coord.x).center;

export function getVerifiedRevenuePlotAreaSize(): { plotW: number; plotH: number } {
  return {
    plotW: VERIFIED_REVENUE_CHART_PLOT_WIDTH,
    plotH: VERIFIED_REVENUE_CHART_PLOT_HEIGHT,
  };
}

export function getVerifiedRevenuePlotUtilization(): number {
  const { plotW, plotH } = getVerifiedRevenuePlotAreaSize();
  return (plotW * plotH) / (VERIFIED_REVENUE_CHART_WIDTH * VERIFIED_REVENUE_CHART_HEIGHT);
}

export function findNearestPointIndexFromPlotX(plotX: number, coords: ChartPlotCoord[]): number {
  if (coords.length === 0) return -1;
  if (coords.length === 1) return 0;
  return plotCoordBisector(coords, plotX);
}

export function resolveVerifiedRevenueYDomain(points: TrendPoint[]): {
  yMinMinor: bigint;
  yMaxMinor: bigint;
} {
  const plottable = points.filter((point) => point.status !== 'unavailable');
  const hasZero = plottable.some((point) => point.status === 'zero' || point.verifiedRevenueMinor === 0n);
  const values = plottable.map((point) => point.verifiedRevenueMinor);
  const dataMin = values.length > 0 ? values.reduce((a, b) => (a < b ? a : b)) : VERIFIED_REVENUE_AXIS_MIN_MINOR;
  const dataMax = values.length > 0 ? values.reduce((a, b) => (a > b ? a : b)) : VERIFIED_REVENUE_AXIS_MAX_MINOR;

  let yMinMinor = hasZero ? 0n : VERIFIED_REVENUE_AXIS_MIN_MINOR;
  let yMaxMinor = VERIFIED_REVENUE_AXIS_MAX_MINOR;

  if (dataMax > yMaxMinor) {
    const overflowStep = ((dataMax - yMaxMinor) / VERIFIED_REVENUE_AXIS_STEP_MINOR + 1n) * VERIFIED_REVENUE_AXIS_STEP_MINOR;
    yMaxMinor = yMaxMinor + overflowStep;
  }
  if (!hasZero && dataMin < yMinMinor) {
    yMinMinor = dataMin;
  }
  if (hasZero && dataMax > 0n && dataMax < VERIFIED_REVENUE_AXIS_MIN_MINOR) {
    yMaxMinor = VERIFIED_REVENUE_AXIS_MIN_MINOR;
  }

  return { yMinMinor, yMaxMinor };
}

function buildYTicksForDomain(yMinMinor: bigint, yMaxMinor: bigint): bigint[] {
  const ticks: bigint[] = [];
  for (let value = yMinMinor; value <= yMaxMinor; value += VERIFIED_REVENUE_AXIS_STEP_MINOR) {
    ticks.push(value);
  }
  if (ticks.length < 2) {
    ticks.push(yMaxMinor);
  }
  return ticks;
}

function buildLineSegments(coords: ChartPlotCoord[]): string[] {
  const segments: string[] = [];
  let current: ChartPlotCoord[] = [];

  for (const coord of coords) {
    if (coord.point.status === 'unavailable') {
      if (current.length > 0) {
        segments.push(line<ChartPlotCoord>().x((c) => c.x).y((c) => c.y).curve(curveLinear)(current) ?? '');
        current = [];
      }
      continue;
    }
    current.push(coord);
  }
  if (current.length > 0) {
    segments.push(line<ChartPlotCoord>().x((c) => c.x).y((c) => c.y).curve(curveLinear)(current) ?? '');
  }
  return segments.filter(Boolean);
}

function buildAreaSegments(coords: ChartPlotCoord[], plotBottom: number): string[] {
  const segments: string[] = [];
  let current: ChartPlotCoord[] = [];

  for (const coord of coords) {
    if (coord.point.status === 'unavailable') {
      if (current.length > 0) {
        segments.push(
          area<ChartPlotCoord>()
            .x((c) => c.x)
            .y0(plotBottom)
            .y1((c) => c.y)
            .curve(curveLinear)(current) ?? '',
        );
        current = [];
      }
      continue;
    }
    current.push(coord);
  }
  if (current.length > 0) {
    segments.push(
      area<ChartPlotCoord>()
        .x((c) => c.x)
        .y0(plotBottom)
        .y1((c) => c.y)
        .curve(curveLinear)(current) ?? '',
    );
  }
  return segments.filter(Boolean);
}

function buildClaimedLineSegments(coords: ChartPlotCoord[], y: ScaleLinear<number, number>): string[] {
  const claimedCoords = coords.filter(
    (coord) =>
      coord.point.status !== 'unavailable' &&
      coord.point.claimedRevenueMinor != null &&
      coord.point.claimedRevenueMinor > 0n,
  );
  if (claimedCoords.length === 0) return [];

  const mapped = claimedCoords.map((coord) => ({
    ...coord,
    y: y(Number(coord.point.claimedRevenueMinor))!,
  }));

  return buildLineSegments(mapped);
}

export function buildReferenceTrendPoints(): TrendPoint[] {
  return buildB210RevenueSnapshotSeries();
}

export function buildVerifiedRevenueChartGeometry(points: TrendPoint[]): {
  lineSegments: string[];
  areaSegments: string[];
  claimedLineSegments: string[];
  yTicks: ChartYTick[];
  xLabels: ChartAxisLabel[];
  coords: ChartPlotCoord[];
  gapMarkers: ChartGapMarker[];
  minDate: string;
  maxDate: string;
  /** @deprecated Single-path alias — first segment only; gaps produce multiple segments. */
  path: string;
  /** @deprecated Single-path alias — first segment only. */
  areaPath: string;
} {
  if (points.length === 0) {
    return {
      lineSegments: [],
      areaSegments: [],
      claimedLineSegments: [],
      path: '',
      areaPath: '',
      yTicks: [],
      xLabels: [],
      coords: [],
      gapMarkers: [],
      minDate: '',
      maxDate: '',
    };
  }

  const sorted = [...points].sort((a, b) => a.windowStartAt.localeCompare(b.windowStartAt));
  const minDate = sorted[0]!.date;
  const maxDate = sorted[sorted.length - 1]!.date;
  const { yMinMinor, yMaxMinor } = resolveVerifiedRevenueYDomain(sorted);
  const { x, y, plotBottom } = createVerifiedRevenueChartScales(
    sorted[0]!.windowStartAt,
    sorted[sorted.length - 1]!.windowEndAt,
    yMinMinor,
    yMaxMinor,
  );

  const coords: ChartPlotCoord[] = sorted.map((point, index) => ({
    x: x(trendPointPlotTime(point))!,
    y:
      point.status === 'unavailable'
        ? y(Number(yMinMinor))!
        : y(Number(point.verifiedRevenueMinor))!,
    point,
    index,
  }));

  const lineSegments = buildLineSegments(coords);
  const areaSegments = buildAreaSegments(coords, plotBottom);
  const claimedLineSegments = buildClaimedLineSegments(coords, y);

  const gapMarkers: ChartGapMarker[] = coords
    .filter((coord) => coord.point.status === 'unavailable')
    .map((coord) => ({
      x: coord.x,
      y: coord.y - VERIFIED_REVENUE_CHART_AXIS.gapMarkerBaselineInset,
      point: coord.point,
      index: coord.index,
    }));

  const yTickMinors = buildYTicksForDomain(yMinMinor, yMaxMinor);
  const yTicks = yTickMinors.map((tickMinor) => ({
    y: y(Number(tickMinor))!,
    label: formatVerifiedRevenueAxisLabel(tickMinor),
  }));

  const labelDates = buildGridAlignedAxisLabelDates(minDate, maxDate, VERIFIED_REVENUE_GRID_X_INTERVALS);
  const xLabels: ChartAxisLabel[] = [];
  for (let labelIndex = 0; labelIndex < labelDates.length; labelIndex += 1) {
    const date = labelDates[labelIndex]!;
    const point = sorted.find((entry) => entry.date === date);
    if (!point) {
      continue;
    }
    xLabels.push({
      date: point.date,
      x: buildGridAlignedAxisLabelX(labelIndex),
      label: formatTrendAxisCompactLabel(point),
      labelY: VERIFIED_REVENUE_CHART_AXIS.xLabelY,
      rotation: VERIFIED_REVENUE_CHART_AXIS.xLabelRotation,
      textAnchor: 'start',
    });
  }

  return {
    lineSegments,
    areaSegments,
    claimedLineSegments,
    path: lineSegments[0] ?? '',
    areaPath: areaSegments[0] ?? '',
    yTicks,
    xLabels,
    coords,
    gapMarkers,
    minDate,
    maxDate,
  };
}

export function analyzeReferenceTrendDynamics(dayCount = TREND_CHART_REFERENCE_DAY_COUNT): {
  downDays: number;
  plateauRuns: number;
  netGrowthMinor: bigint;
  hasMacroDip: boolean;
} {
  const values = Array.from({ length: dayCount }, (_, dayIndex) => buildDailyVerifiedRevenueMinor(dayIndex));
  let downDays = 0;
  let plateauRuns = 0;
  let currentPlateauRun = 1;

  for (let index = 1; index < values.length; index += 1) {
    const previous = values[index - 1]!;
    const current = values[index]!;
    if (current < previous) downDays += 1;

    const delta = current > previous ? current - previous : previous - current;
    if (delta <= 35_000n) {
      currentPlateauRun += 1;
    } else {
      if (currentPlateauRun >= 3) plateauRuns += 1;
      currentPlateauRun = 1;
    }
  }

  if (currentPlateauRun >= 3) plateauRuns += 1;

  const macro = Array.from({ length: dayCount }, (_, dayIndex) => interpolateVerifiedRevenueTrendMinor(dayIndex));
  const hasMacroDip = macro.some((value, index) => index > 0 && value < macro[index - 1]!);

  return {
    downDays,
    plateauRuns,
    netGrowthMinor: values[values.length - 1]! - values[0]!,
    hasMacroDip,
  };
}

export function maxMacroDailyDeltaMinors(dayCount: number): bigint {
  let maxDelta = 0n;
  for (let dayIndex = 1; dayIndex < dayCount; dayIndex += 1) {
    const previous = interpolateVerifiedRevenueTrendMinor(dayIndex - 1);
    const current = interpolateVerifiedRevenueTrendMinor(dayIndex);
    const delta = current > previous ? current - previous : previous - current;
    if (delta > maxDelta) maxDelta = delta;
  }
  return maxDelta;
}

export function maxMacroDailyDeltaInReferenceDateRange(startIso: string, endIso: string): bigint {
  const points = buildReferenceTrendPoints();
  let maxDelta = 0n;

  for (let index = 1; index < points.length; index += 1) {
    const date = points[index]!.date;
    if (date < startIso || date > endIso) continue;

    const prevMacro = interpolateVerifiedRevenueTrendMinor(index - 1);
    const currentMacro = interpolateVerifiedRevenueTrendMinor(index);
    const delta =
      currentMacro > prevMacro ? currentMacro - prevMacro : prevMacro - currentMacro;
    if (delta > maxDelta) maxDelta = delta;
  }

  return maxDelta;
}

export function referenceTrendVerticalSpan(): { minRatio: number; maxRatio: number } {
  const points = buildReferenceTrendPoints();
  const ratios = points.map((point) => verifiedRevenueValueToPlotRatio(point.verifiedRevenueMinor));
  return {
    minRatio: Math.min(...ratios),
    maxRatio: Math.max(...ratios),
  };
}

export function maxDailyRippleDeviationMinors(dayCount: number): bigint {
  let maxDeviation = 0n;
  for (let dayIndex = 0; dayIndex < dayCount; dayIndex += 1) {
    const trendBase = interpolateVerifiedRevenueTrendMinor(dayIndex);
    const actual = buildDailyVerifiedRevenueMinor(dayIndex);
    const deviation = actual > trendBase ? actual - trendBase : trendBase - actual;
    if (deviation > maxDeviation) maxDeviation = deviation;
  }
  return maxDeviation;
}
