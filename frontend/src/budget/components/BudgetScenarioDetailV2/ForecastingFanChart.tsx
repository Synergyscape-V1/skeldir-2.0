import React, { useDeferredValue, useMemo, useState } from 'react';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
  ResponsiveContainer,
  Label,
} from 'recharts';
import {
  CHART_DATA,
  VISIBLE_LABELS,
  MATRIX_DEFAULT_TOTAL_BUDGET,
  type ChartDataPoint,
  type MatrixParametersSnapshot,
} from './scenarioData';

/** Fan band fills — tuned for legibility (inner vs outer must read at a glance). Same order as draw: outer first, inner on top. */
export const FAN_BAND_OUTER_FILL = 'rgba(59, 130, 246, 0.22)'; /* blue-500 — 10–90% envelope */
export const FAN_BAND_INNER_FILL = 'rgba(30, 64, 175, 0.42)'; /* blue-800 — 25–75% core */

/** Skeldir Interface Spec v1.0 — metric selector options. */
export const FAN_METRIC_OPTIONS = [
  { id: 'revenue', label: 'Monthly Revenue ($K)', short: 'Revenue ($K)' },
  { id: 'roas', label: 'ROAS', short: 'ROAS' },
  { id: 'cpl', label: 'CPL', short: 'CPL ($)' },
  { id: 'conversions', label: 'Conversions', short: 'Conversions' },
] as const;

export type FanMetricId = (typeof FAN_METRIC_OPTIONS)[number]['id'];

function scaleChartByBudget(data: ChartDataPoint[], totalBudget: number): ChartDataPoint[] {
  const f = totalBudget / MATRIX_DEFAULT_TOTAL_BUDGET;
  return data.map((p) => ({
    ...p,
    hist: p.hist != null ? Math.round(p.hist * f * 10) / 10 : null,
    med: p.med != null ? Math.round(p.med * f * 10) / 10 : null,
    ciLow: p.ciLow != null ? Math.round(p.ciLow * f * 10) / 10 : null,
    ciHigh: p.ciHigh != null ? Math.round(p.ciHigh * f * 10) / 10 : null,
  }));
}

/** Map illustrative $K series to other metrics for UI preview (API will replace). */
function applyMetricView(raw: number, metric: FanMetricId): number {
  switch (metric) {
    case 'revenue':
      return raw;
    case 'roas':
      return Math.round((raw / 12 + 1.2) * 100) / 100;
    case 'cpl':
      return Math.max(8, Math.round((120 - raw * 1.1) * 10) / 10);
    case 'conversions':
      return Math.round(raw * 42);
    default:
      return raw;
  }
}

/** Format a value already in “display units” for the active metric. */
function formatTooltipDisplay(metric: FanMetricId, displayV: number): string {
  switch (metric) {
    case 'revenue':
      return `$${Math.round(displayV * 1000).toLocaleString()}`;
    case 'roas':
      return `${displayV.toFixed(2)}x`;
    case 'cpl':
      return `$${displayV.toFixed(2)}`;
    case 'conversions':
      return Math.round(displayV).toLocaleString();
    default:
      return String(displayV);
  }
}

function formatYTick(metric: FanMetricId, v: number): string {
  if (metric === 'revenue') return v === 0 ? '0' : String(Math.round(v));
  if (metric === 'roas') return v.toFixed(1);
  if (metric === 'cpl') return String(Math.round(v));
  return String(Math.round(v));
}

/* ─── Custom Tooltip (percentiles, JetBrains Mono) ─── */
function FanChartTooltip({
  active,
  payload,
  metric,
}: {
  active?: boolean;
  payload?: any[];
  metric: FanMetricId;
}) {
  if (!active || !payload || !payload.length) return null;

  const dp = payload[0]?.payload as Record<string, unknown>;
  const dateStr = (dp.tooltipDate as string) || String(dp.x);
  const isHistorical = dp.histViz != null && dp.medLinear == null;
  const isProjected = dp.medLinear != null;

  return (
    <div className="bsdv2-tooltip bsdv2-tooltip--fan">
      <p className="bsdv2-tooltip-header bsdv2-tooltip-header--fan">{dateStr}</p>
      {isHistorical && typeof dp.histViz === 'number' && (
        <div className="bsdv2-tooltip-rows">
          <TooltipRow label="Actual" value={formatTooltipDisplay(metric, dp.histViz)} bold />
        </div>
      )}
      {isProjected && (
        <div className="bsdv2-tooltip-rows">
          <TooltipRow label="Median" value={formatTooltipDisplay(metric, dp.medLinear as number)} bold />
          <div className="bsdv2-tooltip-divider" />
          <TooltipRow label="10th percentile" value={formatTooltipDisplay(metric, dp.p10 as number)} dim />
          <TooltipRow label="25th percentile" value={formatTooltipDisplay(metric, dp.p25 as number)} dim />
          <TooltipRow label="75th percentile" value={formatTooltipDisplay(metric, dp.p75 as number)} dim />
          <TooltipRow label="90th percentile" value={formatTooltipDisplay(metric, dp.p90 as number)} dim />
        </div>
      )}
    </div>
  );
}

function TooltipRow({ label, value, bold, dim }: { label: string; value: string; bold?: boolean; dim?: boolean }) {
  return (
    <div className="bsdv2-tooltip-row">
      <span className={dim ? 'bsdv2-tooltip-label bsdv2-tooltip-label--dim' : 'bsdv2-tooltip-label bsdv2-tooltip-label--normal'}>
        {label}
      </span>
      <span className={bold ? 'bsdv2-tooltip-value bsdv2-tooltip-value--bold' : 'bsdv2-tooltip-value bsdv2-tooltip-value--normal'}>
        {value}
      </span>
    </div>
  );
}

/** “Today” label below the plot (centered on the divider). Recharts passes x + viewBox. */
function TodayLabel(props: { viewBox?: { x?: number; y?: number; width?: number; height?: number }; x?: number; y?: number }) {
  const vb = props.viewBox;
  const cx = (props.x ?? vb?.x ?? 0) as number;
  const yBase = (vb?.y ?? 0) + (vb?.height ?? 0) + 18;
  return (
    <text
      x={cx}
      y={yBase}
      textAnchor="middle"
      style={{
        fill: 'var(--bsdv2-border-strong)',
        fontSize: 12,
        fontFamily: '"DM Sans", sans-serif',
        fontWeight: 600,
      }}
    >
      Today
    </text>
  );
}

function FanChartLegend() {
  return (
    <section className="bsdv2-fan-chart-legend" aria-labelledby="bsdv2-fan-chart-legend-heading" aria-live="polite">
      <h3 id="bsdv2-fan-chart-legend-heading" className="bsdv2-fan-chart-legend-title">
        What the shading means
      </h3>

      <ul className="bsdv2-fan-chart-legend-rows">
        <li className="bsdv2-fan-chart-legend-row">
          <div className="bsdv2-fan-chart-legend-swatch-cell" aria-hidden>
            <span className="bsdv2-fan-chart-legend-swatch-outer" title="Outer band" />
          </div>
          <div className="bsdv2-fan-chart-legend-row-text">
            <span className="bsdv2-fan-chart-legend-row-label">Outer band</span>
            <span className="bsdv2-fan-chart-legend-row-desc">
              10th–90th percentile — full plausible range (80% highest density interval).
            </span>
          </div>
        </li>
        <li className="bsdv2-fan-chart-legend-row">
          <div className="bsdv2-fan-chart-legend-swatch-cell" aria-hidden>
            <span className="bsdv2-fan-chart-legend-swatch-inner" title="Inner band" />
          </div>
          <div className="bsdv2-fan-chart-legend-row-text">
            <span className="bsdv2-fan-chart-legend-row-label">Inner band</span>
            <span className="bsdv2-fan-chart-legend-row-desc">
              25th–75th percentile — where outcomes are most concentrated.
            </span>
          </div>
        </li>
      </ul>

      <p className="bsdv2-fan-chart-legend-note">
        Ranges are model estimates (Bayesian). Bands widen over time because forecast uncertainty grows with the horizon — not because precision is low at every step.
      </p>
    </section>
  );
}

function TimelineBridge() {
  return (
    <div className="bsdv2-chart-timeline-bridge" aria-hidden>
      <span className="bsdv2-chart-timeline-bridge-hist">Historical</span>
      <span className="bsdv2-chart-timeline-bridge-line" />
      <span className="bsdv2-chart-timeline-bridge-today">Today</span>
      <span className="bsdv2-chart-timeline-bridge-line" />
      <span className="bsdv2-chart-timeline-bridge-proj">Projected →</span>
    </div>
  );
}

export interface ForecastingFanChartProps {
  /** Drives rescaling until API projections are wired. */
  matrixSnapshot?: MatrixParametersSnapshot;
}

export function ForecastingFanChart({ matrixSnapshot }: ForecastingFanChartProps) {
  const deferredSnapshot = useDeferredValue(matrixSnapshot);
  const [metric, setMetric] = useState<FanMetricId>('revenue');

  const BOUNDARY = 'Today';
  const baseBudget = deferredSnapshot?.totalBudget ?? MATRIX_DEFAULT_TOTAL_BUDGET;

  const scaledSource = useMemo(() => scaleChartByBudget(CHART_DATA, baseBudget), [baseBudget]);

  const todayIndex = scaledSource.findIndex((point) => point.x === BOUNDARY);
  const projectedIndex = scaledSource.findIndex((point) => point.x === 'Jun');
  const horizonSpan = Math.max(projectedIndex - todayIndex, 1);
  const todayPoint = todayIndex >= 0 ? scaledSource[todayIndex] : null;
  const projectedPoint = projectedIndex >= 0 ? scaledSource[projectedIndex] : null;
  const todayMedian = todayPoint?.med ?? 0;
  const projectedMedian = projectedPoint?.med ?? todayMedian;
  const projectedUpper = projectedPoint?.ciHigh ?? projectedMedian;
  const projectedLower = projectedPoint?.ciLow ?? projectedMedian;

  const yMaxRawDollars = useMemo(() => {
    let m = 0;
    for (const p of scaledSource) {
      if (p.hist != null) m = Math.max(m, p.hist);
      if (p.med != null) m = Math.max(m, p.med);
      if (p.ciHigh != null) m = Math.max(m, p.ciHigh);
    }
    return Math.ceil(Math.max(80, m) / 10) * 10;
  }, [scaledSource]);

  const yDomainMax = useMemo(() => {
    let m = 0;
    for (const p of scaledSource) {
      if (p.hist != null) m = Math.max(m, applyMetricView(p.hist, metric));
      if (p.med != null) m = Math.max(m, applyMetricView(p.med, metric));
      if (p.ciHigh != null) m = Math.max(m, applyMetricView(p.ciHigh, metric));
    }
    const ceil = Math.ceil(m / 10) * 10;
    return Math.max(80, ceil);
  }, [scaledSource, metric]);

  const Y_DOMAIN_MIN = 0;

  const finalUpperSpread = Math.max(projectedUpper - projectedMedian, yMaxRawDollars - projectedMedian, 0);
  const finalLowerSpread = Math.max(projectedMedian - projectedLower, projectedMedian - Y_DOMAIN_MIN, 0);

  const chartData = useMemo(() => {
    const innerFactor = 0.34;

    const rows = scaledSource.map((point, index) => {
      if (point.med === null || point.ciLow === null || point.ciHigh === null) {
        return {
          ...point,
          histViz: point.hist != null ? applyMetricView(point.hist, metric) : null,
          medLinear: null as number | null,
          bandInner: null as [number, number] | null,
          bandOuter: null as [number, number] | null,
          p10: null as number | null,
          p25: null as number | null,
          p50: null as number | null,
          p75: null as number | null,
          p90: null as number | null,
        };
      }

      const t = Math.min(Math.max((index - todayIndex) / horizonSpan, 0), 1);
      const fanMedian = todayMedian + (projectedMedian - todayMedian) * t;
      const upperSpread = finalUpperSpread * t;
      const lowerSpread = finalLowerSpread * t;

      const upperInner = fanMedian + upperSpread * innerFactor;
      const upperOuter = fanMedian + upperSpread;
      const lowerInner = fanMedian - lowerSpread * innerFactor;
      const lowerOuter = fanMedian - lowerSpread;

      const fanMedianV = applyMetricView(fanMedian, metric);
      const p10 = applyMetricView(lowerOuter, metric);
      const p25 = applyMetricView(lowerInner, metric);
      const p50 = fanMedianV;
      const p75 = applyMetricView(upperInner, metric);
      const p90 = applyMetricView(upperOuter, metric);

      return {
        ...point,
        histViz: point.hist != null ? applyMetricView(point.hist, metric) : null,
        medLinear: fanMedianV,
        bandInner: [p25, p75] as [number, number],
        bandOuter: [p10, p90] as [number, number],
        p10,
        p25,
        p50,
        p75,
        p90,
      };
    });

    return rows;
  }, [scaledSource, todayIndex, horizonSpan, todayMedian, projectedMedian, projectedUpper, projectedLower, finalUpperSpread, finalLowerSpread, metric]);

  const metricOption = FAN_METRIC_OPTIONS.find((o) => o.id === metric)!;
  const yLabel = metricOption.short;

  return (
    <div className="bsdv2-panel bsdv2-panel--fan-chart" style={{ fontFamily: '"DM Sans", sans-serif' }}>
      <div className="bsdv2-fan-chart-header">
        <div className="bsdv2-fan-chart-header-row">
          <h2 className="bsdv2-panel-title">Forecasting Fan Chart</h2>
          <label className="bsdv2-fan-chart-metric">
            <span className="bsdv2-sr-only">Metric</span>
            <select
              className="bsdv2-fan-chart-metric-select"
              value={metric}
              onChange={(e) => setMetric(e.target.value as FanMetricId)}
              aria-label="Chart metric"
            >
              {FAN_METRIC_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="bsdv2-fan-chart-metric-subtitle">
          Metric: <span className="bsdv2-fan-chart-metric-subtitle-value">{metricOption.label}</span>
        </p>
      </div>

      <div className="bsdv2-chart-body">
        <div className="bsdv2-zone-labels">
          <span className="bsdv2-zone-label bsdv2-zone-label--left">Historical</span>
          <span className="bsdv2-zone-label bsdv2-zone-label--right">Projected</span>
        </div>

        <div className="bsdv2-chart-wrapper">
          <ResponsiveContainer width="100%" height={390}>
            <ComposedChart data={chartData} margin={{ top: 12, right: 44, left: 8, bottom: 36 }}>
              <CartesianGrid vertical={false} strokeDasharray="4 4" stroke="var(--bsdv2-border-subtle)" strokeWidth={1} />
              <XAxis
                dataKey="x"
                tick={({ x, y, payload }: any) => {
                  if (!VISIBLE_LABELS.has(payload.value)) return <g />;
                  return (
                    <text
                      x={x}
                      y={y + 12}
                      textAnchor="middle"
                      style={{
                        fill: 'var(--bsdv2-text-tertiary)',
                        fontSize: 12,
                        fontWeight: 600,
                        fontFamily: '"JetBrains Mono", monospace',
                      }}
                    >
                      {payload.value}
                    </text>
                  );
                }}
                axisLine={{ stroke: 'var(--bsdv2-border-subtle)' }}
                tickLine={false}
              />
              <YAxis
                domain={[0, yDomainMax]}
                tickFormatter={(v: number) => formatYTick(metric, v)}
                tick={{ fill: 'var(--bsdv2-text-tertiary)', fontSize: 12, fontWeight: 600, fontFamily: '"JetBrains Mono", monospace' }}
                axisLine={false}
                tickLine={false}
                width={44}
                label={
                  <Label
                    value={yLabel}
                    angle={-90}
                    position="insideLeft"
                    style={{
                      fill: 'var(--bsdv2-text-tertiary)',
                      fontSize: 12,
                      fontWeight: 600,
                      fontFamily: '"DM Sans", sans-serif',
                    }}
                  />
                }
              />

              {/* Outer band first (10–90), inner (25–75) on top — fill only */}
              <Area
                type="linear"
                dataKey="bandOuter"
                fill={FAN_BAND_OUTER_FILL}
                stroke="none"
                activeDot={false}
                isAnimationActive
                animationDuration={200}
                animationEasing="ease-out"
              />
              <Area
                type="linear"
                dataKey="bandInner"
                fill={FAN_BAND_INNER_FILL}
                stroke="none"
                activeDot={false}
                isAnimationActive
                animationDuration={200}
                animationEasing="ease-out"
              />

              <ReferenceArea x1="Jan" x2="Mar" fill="rgba(248, 250, 252, 0.6)" stroke="none" />
              <ReferenceArea x1="Today" x2="Jun" fill="rgba(239, 246, 255, 0.3)" stroke="none" />

              <Line
                type="monotone"
                dataKey="histViz"
                stroke="var(--bsdv2-data-1)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: 'var(--bsdv2-data-1)', strokeWidth: 0 }}
                connectNulls={false}
                isAnimationActive
                animationDuration={200}
                animationEasing="ease-out"
              />

              <Line
                type="linear"
                dataKey="medLinear"
                stroke="var(--bsdv2-data-1)"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                activeDot={{ r: 4, fill: 'var(--bsdv2-data-1)', stroke: 'var(--bsdv2-bg-surface)', strokeWidth: 2 }}
                connectNulls={false}
                isAnimationActive
                animationDuration={200}
                animationEasing="ease-out"
              />

              <ReferenceLine
                x={BOUNDARY}
                stroke="var(--bsdv2-border-strong)"
                strokeWidth={1}
                strokeDasharray="6 6"
                ifOverflow="extendDomain"
                zIndex={10}
                label={(labelProps: { viewBox?: { x?: number; y?: number; height?: number }; x?: number }) => (
                  <TodayLabel {...labelProps} />
                )}
              />

              <Tooltip
                content={<FanChartTooltip metric={metric} />}
                cursor={{ stroke: 'var(--bsdv2-border-strong)', strokeWidth: 1, strokeDasharray: '4 2' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <TimelineBridge />

        <div className="bsdv2-chart-xlabel">
          <span>Time (months)</span>
        </div>

        <FanChartLegend />
      </div>
    </div>
  );
}
