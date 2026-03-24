import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CircleHelp, Download, Layers, LayoutList } from "lucide-react";
import PlatformIcon from "./PlatformIcon";
import { CHANNEL_BAR_COLORS, DATA_COLORS } from "./types";
import type { ChannelData } from "./types";
import "./ci-overlap-chart.css";
import {
  CC_ROAS_SCALE,
  buildComparisonTicks,
  channelDataToRows,
  findMaxOverlapPair,
  sortRows,
  type CredibleIntervalBarProps,
  type ROASBucket,
  type ROASChannelRow,
  type ROASSortMode,
  type ROASViewMode,
} from "./ciOverlapTypes";

/** Visual bar height — match original CI overlap chart (slim strips). */
const BAR_H = 12;
/** Central high-density mass band as a fraction of the HDI width (original encoding). */
const INNER_FRAC = 0.44;
const AXIS_H = 36;

const BUCKET_STYLES: Record<
  ROASBucket,
  { fill: string; stroke: string; label: string; icon: string; action: string }
> = {
  narrow: {
    fill: "rgba(5, 150, 105, 0.08)",
    stroke: "rgba(5, 150, 105, 0.3)",
    label: "High confidence",
    icon: "\u2713",
    action: "Safe to scale — narrow 80% HDI vs median.",
  },
  medium: {
    fill: "rgba(217, 119, 6, 0.08)",
    stroke: "rgba(217, 119, 6, 0.3)",
    label: "Moderate",
    icon: "\u25C9",
    action: "Monitor 1–2 weeks before major reallocations.",
  },
  wide: {
    fill: "rgba(220, 38, 38, 0.08)",
    stroke: "rgba(220, 38, 38, 0.3)",
    label: "Low confidence",
    icon: "\u26A0",
    action: "Insufficient precision — gather more signal before acting.",
  },
};

function toX(v: number, scaleMin: number, scaleMax: number, plotW: number): number {
  const r = scaleMax - scaleMin || 1;
  return ((v - scaleMin) / r) * plotW;
}

/**
 * HDI bar — original channel-comparison encoding:
 * lighter outer interval, darker inner “high-density” band, solid point estimate in channel color.
 */
export function CredibleIntervalBar({
  pointEstimate,
  lower,
  upper,
  scaleMin,
  scaleMax,
  colorIndex,
  showPointEstimate,
  isOverlayMode,
  plotWidth,
  barHeight,
  yOffset,
}: CredibleIntervalBarProps) {
  const color = DATA_COLORS[colorIndex] ?? "#64748B";
  const barColors = CHANNEL_BAR_COLORS[colorIndex] ?? {
    dark: "var(--text-secondary)",
    light: "var(--border-default)",
  };

  const x1 = toX(lower, scaleMin, scaleMax, plotWidth);
  const x2 = toX(upper, scaleMin, scaleMax, plotWidth);
  const xEst = toX(pointEstimate, scaleMin, scaleMax, plotWidth);
  const barW = Math.max(4, x2 - x1);

  const range = Math.max(0.0001, upper - lower);
  const innerHalf = (range * INNER_FRAC) / 2;
  const innerLower = Math.max(lower, pointEstimate - innerHalf);
  const innerUpper = Math.min(upper, pointEstimate + innerHalf);
  const ix1 = toX(innerLower, scaleMin, scaleMax, plotWidth);
  const ix2 = toX(innerUpper, scaleMin, scaleMax, plotWidth);
  const innerW = Math.max(2, ix2 - ix1);

  const opacity = isOverlayMode ? 0.88 : 1;

  return (
    <g opacity={opacity}>
      <rect
        x={x1}
        y={yOffset}
        width={barW}
        height={barHeight}
        fill={barColors.light}
        fillOpacity={isOverlayMode ? 0.38 : 0.32}
        stroke={color}
        strokeOpacity={isOverlayMode ? 0.65 : 0.55}
        strokeWidth={1}
        rx={3}
      />
      <rect
        x={ix1}
        y={yOffset}
        width={innerW}
        height={barHeight}
        fill={barColors.dark}
        fillOpacity={isOverlayMode ? 0.55 : 0.5}
        rx={3}
      />
      {showPointEstimate && (
        <rect
          x={xEst - 1}
          y={yOffset}
          width={2}
          height={barHeight}
          fill={color}
          fillOpacity={1}
        />
      )}
    </g>
  );
}

export interface CIOverlapChartProps {
  channels: ChannelData[];
  confidenceLevel?: number;
  periodLabel?: string;
  initialViewMode?: ROASViewMode;
  initialSortBy?: ROASSortMode;
  /** Increment (e.g. parent state++) to open overlay mode — “Compare selected” flow. */
  openOverlaySignal?: number;
  onChannelSelect?: (id: string) => void;
  onExport?: () => void;
}

export default function CIOverlapChart({
  channels,
  confidenceLevel = 0.8,
  periodLabel = "Last 30 days",
  initialViewMode = "aligned",
  initialSortBy = "priority",
  openOverlaySignal = 0,
  onChannelSelect,
  onExport,
}: CIOverlapChartProps) {
  const plotRef = useRef<HTMLDivElement>(null);
  const [plotW, setPlotW] = useState(520);
  const [viewMode, setViewMode] = useState<ROASViewMode>(initialViewMode);
  const [sortBy, setSortBy] = useState<ROASSortMode>(initialSortBy);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (openOverlaySignal > 0) setViewMode("overlay");
  }, [openOverlaySignal]);

  useEffect(() => {
    const el = plotRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 520;
      setPlotW(Math.max(160, Math.floor(w)));
    });
    ro.observe(el);
    setPlotW(Math.max(160, Math.floor(el.getBoundingClientRect().width)));
    return () => ro.disconnect();
  }, [viewMode]);

  const rows = useMemo(() => {
    const base = channelDataToRows(channels, (platform) => (
      <PlatformIcon platform={platform} size={20} />
    ));
    return sortRows(base, sortBy);
  }, [channels, sortBy]);

  const scaleMin = CC_ROAS_SCALE.min;
  const scaleMax = CC_ROAS_SCALE.max;
  const ticks = useMemo(() => buildComparisonTicks(scaleMin, scaleMax, 0.5), [scaleMin, scaleMax]);

  const overlapInsight = useMemo(() => findMaxOverlapPair(rows), [rows]);

  const handleRowClick = useCallback(
    (id: string) => {
      setSelectedId((prev) => (prev === id ? null : id));
      onChannelSelect?.(id);
    },
    [onChannelSelect]
  );

  const pctLabel = `${Math.round(confidenceLevel * 100)}%`;

  if (!channels?.length) return null;

  /** Vertical space above shared axis in overlay mode (slim 12px bars + padding). */
  const overlayBandH = 22;

  return (
    <section
      id="cc-roas-ci"
      className="cc-roas-ci"
      aria-label={`ROAS credible interval comparison, ${pctLabel} highest density interval`}
    >
      <div className="cc-roas-ci__header">
        <div className="cc-roas-ci__title-block">
          <h2 className="cc-roas-ci__title">ROAS Credible Interval Comparison</h2>
          <p className="cc-roas-ci__subtitle">
            {pctLabel} Highest Density Interval — {periodLabel} — Bayesian attribution model
          </p>
        </div>
        <div className="cc-roas-ci__toolbar">
          <button
            type="button"
            className="cc-roas-ci__btn"
            title={`Uncertainty is shown as the ${pctLabel} HDI; the dashed line is the posterior median (secondary).`}
            aria-label="About this chart"
          >
            <CircleHelp size={14} strokeWidth={2} aria-hidden />
          </button>
          <button
            type="button"
            className="cc-roas-ci__btn"
            onClick={() => onExport?.()}
            disabled={!onExport}
            title={onExport ? "Export comparison" : "Export available from the page header"}
          >
            <Download size={14} strokeWidth={2} aria-hidden />
            Export
          </button>
          <div style={{ width: 1, height: 18, background: "var(--border-subtle, #e2e8f0)" }} aria-hidden />
          <button
            type="button"
            className={`cc-roas-ci__btn ${viewMode === "aligned" ? "" : ""}`}
            onClick={() => setViewMode("aligned")}
            aria-pressed={viewMode === "aligned"}
            title="Side-by-side rows (default)"
          >
            <LayoutList size={14} aria-hidden /> Aligned
          </button>
          <button
            type="button"
            className="cc-roas-ci__btn"
            onClick={() => setViewMode("overlay")}
            aria-pressed={viewMode === "overlay"}
            title="Overlap all intervals on one scale"
          >
            <Layers size={14} aria-hidden /> Overlay
          </button>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <span style={{ color: "var(--text-secondary, #64748b)" }}>Sort</span>
            <select
              className="cc-roas-ci__select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as ROASSortMode)}
              aria-label="Sort channels"
            >
              <option value="priority">Priority (certainty)</option>
              <option value="point_estimate">Point estimate (median)</option>
              <option value="lower_bound">Lower bound (conservative)</option>
              <option value="confidence_width">Interval width (ascending)</option>
            </select>
          </label>
        </div>
      </div>

      <div className="cc-roas-ci__legend" role="group" aria-label="Legend">
        <span className="cc-roas-ci__legend-item">
          <span className="cc-roas-ci__legend-swatch cc-roas-ci__legend-swatch--interval" aria-hidden />
          <span>Credible interval ({pctLabel} HDI)</span>
        </span>
        <span className="cc-roas-ci__legend-item">
          <span className="cc-roas-ci__legend-swatch cc-roas-ci__legend-swatch--point" aria-hidden />
          <span>Point estimate (median)</span>
        </span>
        <span className="cc-roas-ci__legend-buckets" aria-label="Bucket semantics">
          <span>
            <span className="cc-roas-ci__bucket-icon" aria-hidden>
              {BUCKET_STYLES.narrow.icon}
            </span>
            Narrow
          </span>
          <span>
            <span className="cc-roas-ci__bucket-icon" aria-hidden>
              {BUCKET_STYLES.medium.icon}
            </span>
            Medium
          </span>
          <span>
            <span className="cc-roas-ci__bucket-icon" aria-hidden>
              {BUCKET_STYLES.wide.icon}
            </span>
            Wide
          </span>
        </span>
      </div>

      {viewMode === "aligned" ? (
        <>
          <div className="cc-roas-ci__table-wrap">
            <div className="cc-roas-ci__row-grid cc-roas-ci__grid-head" role="row">
              <div className="cc-roas-ci__th" role="columnheader">
                Channel
              </div>
              <div className="cc-roas-ci__th" role="columnheader">
                ROAS range ({scaleMin.toFixed(1)}–{scaleMax.toFixed(1)})
              </div>
              <div className="cc-roas-ci__th cc-roas-ci__th--num" role="columnheader">
                Est.
              </div>
              <div className="cc-roas-ci__th" role="columnheader">
                Bucket
              </div>
            </div>

            {rows.map((row) => (
              <AlignedRow
                key={row.channelId}
                row={row}
                plotW={plotW}
                scaleMin={scaleMin}
                scaleMax={scaleMax}
                selected={selectedId === row.channelId}
                onClick={() => handleRowClick(row.channelId)}
              />
            ))}

            <div className="cc-roas-ci__row-grid cc-roas-ci__axis-footer" role="presentation">
              <div />
              <div ref={plotRef} style={{ paddingTop: 4 }}>
                <svg
                  width={plotW}
                  height={AXIS_H}
                  style={{ display: "block" }}
                  aria-hidden
                >
                  <line
                    x1={0}
                    y1={4}
                    x2={plotW}
                    y2={4}
                    stroke="var(--text-primary, #0f172a)"
                    strokeWidth={2}
                  />
                  {ticks.map((tick) => {
                    const tx = toX(tick, scaleMin, scaleMax, plotW);
                    return (
                      <g key={`ax-${tick}`}>
                        <line
                          x1={tx}
                          y1={4}
                          x2={tx}
                          y2={10}
                          stroke="var(--text-primary, #0f172a)"
                          strokeWidth={2}
                        />
                        <text
                          x={tx}
                          y={26}
                          textAnchor="middle"
                          fontSize={12}
                          fill="var(--text-tertiary, #94a3b8)"
                          fontFamily="var(--font-mono, JetBrains Mono, monospace)"
                          style={{ fontVariantNumeric: "tabular-nums" }}
                        >
                          {tick % 1 === 0 ? tick.toFixed(0) : tick.toFixed(1)}
                        </text>
                      </g>
                    );
                  })}
                </svg>
                <div className="cc-roas-ci__axis-label">ROAS →</div>
              </div>
              <div />
              <div />
            </div>
          </div>

          <footer className="cc-roas-ci__footer">
            <div className="cc-roas-ci__footer-title">Action implications</div>
            <ul className="cc-roas-ci__footer-list">
              {rows.map((r) => (
                <li key={`act-${r.channelId}`}>
                  <strong>{r.channelName}:</strong> {BUCKET_STYLES[r.bucket].action}
                  {r.sampleSizeIndicator === "insufficient" && (
                    <span> Data health: limited posterior evidence.</span>
                  )}
                </li>
              ))}
            </ul>
            {overlapInsight && overlapInsight.pct >= 45 && (
              <p style={{ margin: "8px 0 0", fontSize: 12 }}>
                <strong>Overlap:</strong> {overlapInsight.a.channelName} and {overlapInsight.b.channelName}{" "}
                intervals overlap ~{overlapInsight.pct.toFixed(0)}% of the narrower band — treat “winner”
                claims cautiously at {pctLabel} HDI.
              </p>
            )}
          </footer>
        </>
      ) : (
        <OverlayBlock
          rows={rows}
          plotW={plotW}
          plotRef={plotRef}
          scaleMin={scaleMin}
          scaleMax={scaleMax}
          ticks={ticks}
          bandH={overlayBandH}
          pctLabel={pctLabel}
          overlapInsight={overlapInsight}
        />
      )}

      <style>{`
        .cc-roas-ci__row-grid {
          display: grid;
          grid-template-columns: minmax(160px, 1.1fr) minmax(220px, 2.6fr) 72px minmax(108px, 0.9fr);
          align-items: stretch;
        }
        .cc-roas-ci__grid-head .cc-roas-ci__th {
          border-bottom: 1px solid var(--cc-roas-border, #e2e8f0);
        }
        .cc-roas-ci__grid-row .cc-roas-ci__td {
          border-bottom: 1px solid var(--cc-roas-border, #e2e8f0);
        }
        .cc-roas-ci__axis-footer {
          border-bottom: none;
        }
      `}</style>
    </section>
  );
}

function AlignedRow({
  row,
  plotW,
  scaleMin,
  scaleMax,
  selected,
  onClick,
}: {
  row: ROASChannelRow;
  plotW: number;
  scaleMin: number;
  scaleMax: number;
  selected: boolean;
  onClick: () => void;
}) {
  const interactive = true;
  const aria = `${row.channelName}: ROAS median ${row.roas.formattedPoint}, credible interval ${row.roas.formattedLower} to ${row.roas.formattedUpper}, ${BUCKET_STYLES[row.bucket].label}.`;

  return (
    <div
      className={`cc-roas-ci__row-grid cc-roas-ci__grid-row ${selected ? "cc-roas-ci__row--selected" : ""} ${
        interactive ? "cc-roas-ci__row--interactive" : ""
      }`}
      role="row"
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      tabIndex={0}
      aria-label={aria}
    >
      <div className="cc-roas-ci__td cc-roas-ci__channel-cell" role="cell">
        {row.channelIcon}
        <div>
          <div className="cc-roas-ci__channel-name">{row.channelName}</div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary, #94a3b8)", marginTop: 2 }}>
            {row.attributionModel === "bayesian" ? "Bayesian" : row.attributionModel}
          </div>
        </div>
      </div>
      <div className="cc-roas-ci__td cc-roas-ci__range-cell" role="cell">
        <svg
          width={plotW}
          height={BAR_H + 6}
          className="cc-roas-ci__range-svg"
          style={{ display: "block" }}
          aria-hidden
        >
          <CredibleIntervalBar
            pointEstimate={row.roas.pointEstimate}
            lower={row.roas.lower}
            upper={row.roas.upper}
            scaleMin={scaleMin}
            scaleMax={scaleMax}
            colorIndex={row.colorIndex}
            showPointEstimate
            plotWidth={plotW}
            barHeight={BAR_H}
            yOffset={0}
          />
        </svg>
        <div className="cc-roas-ci__range-bracket">
          [{row.roas.formattedLower} — {row.roas.formattedUpper}]
        </div>
      </div>
      <div className="cc-roas-ci__td cc-roas-ci__point-cell" role="cell">
        {row.roas.formattedPoint}
      </div>
      <div className="cc-roas-ci__td cc-roas-ci__bucket-cell" role="cell">
        <span className={`cc-roas-ci__bucket-pill cc-roas-ci__bucket-pill--${row.bucket}`}>
          <span className="cc-roas-ci__bucket-icon" aria-hidden>
            {BUCKET_STYLES[row.bucket].icon}
          </span>
          {BUCKET_STYLES[row.bucket].label}
        </span>
      </div>
    </div>
  );
}

function OverlayBlock({
  rows,
  plotW,
  plotRef,
  scaleMin,
  scaleMax,
  ticks,
  bandH,
  pctLabel,
  overlapInsight,
}: {
  rows: ROASChannelRow[];
  plotW: number;
  plotRef: React.RefObject<HTMLDivElement | null>;
  scaleMin: number;
  scaleMax: number;
  ticks: number[];
  bandH: number;
  pctLabel: string;
  overlapInsight: ReturnType<typeof findMaxOverlapPair>;
}) {
  const svgH = bandH + AXIS_H + 8;
  const sorted = [...rows].sort((a, b) => a.roas.lower - b.roas.lower);

  return (
    <div className="cc-roas-ci__overlay-block">
      <p style={{ margin: "0 0 8px", fontSize: 12, color: "var(--text-secondary, #64748b)" }}>
        Overlay mode: all {pctLabel} HDI bands share one calibrated horizontal scale (cross-channel calibration).
      </p>
      <div ref={plotRef} style={{ width: "100%" }}>
        <svg
          width="100%"
          height={svgH}
          viewBox={`0 0 ${Math.max(1, plotW)} ${svgH}`}
          preserveAspectRatio="xMinYMid meet"
          aria-label="Overlapping credible intervals"
        >
          {ticks.map((tick) => {
            const tx = toX(tick, scaleMin, scaleMax, plotW);
            return (
              <line
                key={`og-${tick}`}
                x1={tx}
                y1={0}
                x2={tx}
                y2={bandH}
                stroke="var(--border-subtle, #e2e8f0)"
                strokeWidth={1}
              />
            );
          })}
          {sorted.map((row, i) => {
            const o = 0.35 + i * 0.05;
            const y0 = 4;
            return (
              <g key={row.channelId} opacity={Math.min(0.95, o)}>
                <CredibleIntervalBar
                  pointEstimate={row.roas.pointEstimate}
                  lower={row.roas.lower}
                  upper={row.roas.upper}
                  scaleMin={scaleMin}
                  scaleMax={scaleMax}
                  colorIndex={row.colorIndex}
                  showPointEstimate
                  isOverlayMode
                  plotWidth={plotW}
                  barHeight={BAR_H}
                  yOffset={y0}
                />
              </g>
            );
          })}
          <line
            x1={0}
            y1={bandH}
            x2={plotW}
            y2={bandH}
            stroke="var(--text-primary, #0f172a)"
            strokeWidth={2}
          />
          {ticks.map((tick) => {
            const tx = toX(tick, scaleMin, scaleMax, plotW);
            return (
              <g key={`ot-${tick}`}>
                <line x1={tx} y1={bandH} x2={tx} y2={bandH + 6} stroke="var(--text-primary, #0f172a)" strokeWidth={2} />
                <text
                  x={tx}
                  y={bandH + 22}
                  textAnchor="middle"
                  fontSize={12}
                  fill="var(--text-tertiary, #94a3b8)"
                  fontFamily="var(--font-mono, JetBrains Mono, monospace)"
                >
                  {tick % 1 === 0 ? tick.toFixed(0) : tick.toFixed(1)}
                </text>
              </g>
            );
          })}
        </svg>
        <div className="cc-roas-ci__axis-label">ROAS →</div>
      </div>
      <div style={{ marginTop: 10, fontSize: 12, color: "var(--text-secondary)" }}>
        <strong>Channel key:</strong>{" "}
        {rows.map((r) => (
          <span key={r.channelId} style={{ marginRight: 10 }}>
            <span style={{ color: DATA_COLORS[r.colorIndex] ?? "#64748B" }}>●</span> {r.channelName}
          </span>
        ))}
      </div>
      {overlapInsight && (
        <p style={{ margin: "10px 0 0", fontSize: 12 }}>
          <strong>Interpretation:</strong> Largest pairwise overlap is between {overlapInsight.a.channelName} and{" "}
          {overlapInsight.b.channelName} (~{overlapInsight.pct.toFixed(0)}% of the narrower HDI).{" "}
          {overlapInsight.pct > 55
            ? `At ${pctLabel} HDI, do not treat rankings as decisive until intervals separate.`
            : "Intervals are partially distinct — combine with spend and marginal ROAS before reallocating."}
        </p>
      )}
    </div>
  );
}
