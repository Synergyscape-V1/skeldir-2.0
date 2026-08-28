import { useCallback, useId, useMemo, useRef, useState, type PointerEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import type { TrendPoint } from '../../../commandCenter/types';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import { buildTrendDrillDownHref } from '../../../commandCenter/trendDrillDown';
import styles from './VerifiedRevenueChart.module.css';
import {
  VERIFIED_REVENUE_CHART_AXIS,
  VERIFIED_REVENUE_CHART_HEIGHT,
  VERIFIED_REVENUE_CHART_PAD,
  VERIFIED_REVENUE_CHART_PLOT_HEIGHT,
  VERIFIED_REVENUE_CHART_PLOT_WIDTH,
  VERIFIED_REVENUE_CHART_PRESERVE_ASPECT_RATIO,
  VERIFIED_REVENUE_CHART_WIDTH,
  buildVerifiedRevenueChartGeometry,
  findNearestPointIndexFromPlotX,
  formatTrendTooltipLabel,
  mapClientXToViewBoxX,
  mapViewBoxPointToClient,
  resolveGapLabelLayout,
} from './verifiedRevenueChartGeometry';

export interface VerifiedRevenueChartProps {
  points: TrendPoint[];
  currencyCode?: string;
  showClaimedOverlay?: boolean;
}

interface HoverState {
  index: number;
  tooltipLeft: number;
  tooltipTop: number;
  placement: 'above' | 'below';
}

const TOOLTIP_EDGE_PAD = 8;
const TOOLTIP_EST_HALF_WIDTH = 72;
const TOOLTIP_EST_HEIGHT = 52;
const TOOLTIP_GAP = 8;

function clampTooltipAnchor(
  pointLeft: number,
  pointTop: number,
  wrapWidth: number,
  wrapHeight: number,
): Pick<HoverState, 'tooltipLeft' | 'tooltipTop' | 'placement'> {
  const half = TOOLTIP_EST_HALF_WIDTH;
  const minLeft = half + TOOLTIP_EDGE_PAD;
  const maxLeft = Math.max(minLeft, wrapWidth - half - TOOLTIP_EDGE_PAD);
  const tooltipLeft = Math.min(maxLeft, Math.max(minLeft, pointLeft));

  const needsBelow = pointTop < TOOLTIP_EST_HEIGHT + TOOLTIP_GAP + TOOLTIP_EDGE_PAD;
  const placement = needsBelow ? 'below' : 'above';
  const tooltipTop = needsBelow
    ? Math.min(wrapHeight - TOOLTIP_EDGE_PAD, pointTop)
    : Math.max(TOOLTIP_EDGE_PAD, pointTop);

  return { tooltipLeft, tooltipTop, placement };
}

export function VerifiedRevenueChart({
  points,
  currencyCode = 'USD',
  showClaimedOverlay = false,
}: VerifiedRevenueChartProps) {
  const navigate = useNavigate();
  const tooltipId = useId();
  const liveRegionId = useId();
  const fillGradientId = useId().replace(/:/g, '');
  const plotClipId = useId().replace(/:/g, '');
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<HoverState | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);

  const plotW = VERIFIED_REVENUE_CHART_PLOT_WIDTH;
  const plotH = VERIFIED_REVENUE_CHART_PLOT_HEIGHT;

  const geometry = useMemo(() => buildVerifiedRevenueChartGeometry(points), [points]);
  const { lineSegments, areaSegments, claimedLineSegments, yTicks, xLabels, coords, gapMarkers } =
    geometry;

  const labelMarkers = useMemo(() => {
    const labeledDates = new Set(xLabels.map((label) => label.date));
    return coords.filter(
      (coord) => labeledDates.has(coord.point.date) && coord.point.status !== 'unavailable',
    );
  }, [coords, xLabels]);

  const activeIndex = hover?.index ?? focusedIndex;
  const active = activeIndex != null ? coords[activeIndex] : null;

  const resolvePlotXFromClient = useCallback((clientX: number): number | null => {
    const svg = svgRef.current;
    if (!svg) return null;
    return mapClientXToViewBoxX(clientX, svg.getBoundingClientRect());
  }, []);

  const updateHoverFromClient = useCallback(
    (clientX: number, _clientY: number) => {
      const plotX = resolvePlotXFromClient(clientX);
      const wrap = wrapRef.current;
      if (plotX == null || !wrap || coords.length === 0) return;

      const index = findNearestPointIndexFromPlotX(plotX, coords);
      const coord = coords[index];
      if (!coord) return;

      const wrapRect = wrap.getBoundingClientRect();
      const svgRect = svgRef.current?.getBoundingClientRect();
      if (!svgRect) return;

      const mapped = mapViewBoxPointToClient(coord.x, coord.y, svgRect);
      if (!mapped) return;

      setHover({
        index,
        ...clampTooltipAnchor(
          mapped.clientX - wrapRect.left,
          mapped.clientY - wrapRect.top,
          wrapRect.width,
          wrapRect.height,
        ),
      });
    },
    [coords, resolvePlotXFromClient],
  );

  const handlePlotPointerMove = useCallback(
    (event: PointerEvent<SVGRectElement>) => {
      updateHoverFromClient(event.clientX, event.clientY);
    },
    [updateHoverFromClient],
  );

  const handlePlotPointerLeave = useCallback(() => {
    setHover(null);
  }, []);

  const handlePointFocus = useCallback(
    (index: number) => {
      setFocusedIndex(index);
      const coord = coords[index];
      const wrap = wrapRef.current;
      const svg = svgRef.current;
      if (!coord || !wrap || !svg) return;

      const wrapRect = wrap.getBoundingClientRect();
      const svgRect = svg.getBoundingClientRect();
      const mapped = mapViewBoxPointToClient(coord.x, coord.y, svgRect);
      if (!mapped) return;

      setHover({
        index,
        ...clampTooltipAnchor(
          mapped.clientX - wrapRect.left,
          mapped.clientY - wrapRect.top,
          wrapRect.width,
          wrapRect.height,
        ),
      });
    },
    [coords],
  );

  const handlePointActivate = useCallback(
    (point: TrendPoint) => {
      if (point.status === 'unavailable') return;
      navigate(buildTrendDrillDownHref(point));
    },
    [navigate],
  );

  const tooltipContent = active ? formatTrendTooltipLabel(active.point, currencyCode) : null;
  const liveSummary = active
    ? active.point.status === 'unavailable'
      ? `${COMMAND_CENTER_COPY.trendDataUnavailableLabel}: ${active.point.unavailableReason ?? 'Snapshot missing'}`
      : `${tooltipContent?.dateLabel ?? ''}. ${tooltipContent?.primaryValue ?? ''}. ${tooltipContent?.sourceProof ?? ''}. ${tooltipContent?.windowRange ?? ''}`
    : '';

  return (
    <div
      ref={wrapRef}
      className={styles.wrap}
      data-verified-revenue-chart
      data-chart-engine="d3"
      data-trend-day-count={points.length}
      data-trend-line-segments={lineSegments.length}
      data-trend-gap-count={gapMarkers.length}
      data-trend-hover-index={activeIndex ?? undefined}
      data-trend-claimed-overlay={showClaimedOverlay ? 'true' : undefined}
    >
      {showClaimedOverlay ? (
        <div className={styles.legend} data-trend-legend>
          <span className={styles.legendItem}>
            <span className={styles.legendSwatchDeterministic} aria-hidden />
            Deterministic
          </span>
          <span className={styles.legendItem}>
            <span className={styles.legendSwatchClaimed} aria-hidden />
            {COMMAND_CENTER_COPY.platformClaimLabel}
          </span>
        </div>
      ) : null}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${VERIFIED_REVENUE_CHART_WIDTH} ${VERIFIED_REVENUE_CHART_HEIGHT}`}
        className={styles.svg}
        role="img"
        aria-label="Verified revenue trend chart"
        preserveAspectRatio={VERIFIED_REVENUE_CHART_PRESERVE_ASPECT_RATIO}
      >
        <defs>
          <linearGradient id={fillGradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" className={styles.fillStopTop} />
            <stop offset="100%" className={styles.fillStopBottom} />
          </linearGradient>
          <clipPath id={plotClipId}>
            <rect
              x={VERIFIED_REVENUE_CHART_PAD.left}
              y={VERIFIED_REVENUE_CHART_PAD.top}
              width={plotW}
              height={plotH}
            />
          </clipPath>
        </defs>
        {yTicks.map((tick) => (
          <g key={`y-${tick.label}`}>
            <line
              x1={VERIFIED_REVENUE_CHART_PAD.left}
              x2={VERIFIED_REVENUE_CHART_PAD.left + plotW}
              y1={tick.y}
              y2={tick.y}
              className={styles.grid}
              strokeWidth={VERIFIED_REVENUE_CHART_AXIS.gridStrokeWidth}
            />
            <text
              x={VERIFIED_REVENUE_CHART_AXIS.yLabelX}
              y={tick.y}
              className={styles.axisLabel}
              fontSize={VERIFIED_REVENUE_CHART_AXIS.yLabelFontSize}
              textAnchor="end"
              dominantBaseline="middle"
            >
              {tick.label}
            </text>
          </g>
        ))}
        {xLabels.map((label) => (
          <line
            key={`x-grid-${label.date}-${label.x}`}
            x1={label.x}
            x2={label.x}
            y1={VERIFIED_REVENUE_CHART_PAD.top}
            y2={VERIFIED_REVENUE_CHART_PAD.top + plotH}
            className={styles.grid}
            strokeWidth={VERIFIED_REVENUE_CHART_AXIS.gridStrokeWidth}
          />
        ))}
        <g clipPath={`url(#${plotClipId})`}>
        {areaSegments.map((segment, index) => (
          <path
            key={`area-${index}`}
            d={segment}
            className={styles.area}
            style={{ fill: `url(#${fillGradientId})` }}
          />
        ))}
        {lineSegments.map((segment, index) => (
          <path
            key={`line-${index}`}
            d={segment}
            className={styles.line}
            fill="none"
            strokeWidth={VERIFIED_REVENUE_CHART_AXIS.lineStrokeWidth}
            data-trend-line-segment={index}
          />
        ))}
        {showClaimedOverlay
          ? claimedLineSegments.map((segment, index) => (
              <path
                key={`claimed-${index}`}
                d={segment}
                className={styles.claimedLine}
                fill="none"
                strokeWidth={VERIFIED_REVENUE_CHART_AXIS.lineStrokeWidth}
                data-trend-claimed-line-segment={index}
              />
            ))
          : null}
        {labelMarkers.map((coord) => (
          <circle
            key={`label-marker-${coord.point.date}`}
            cx={coord.x}
            cy={coord.y}
            r={VERIFIED_REVENUE_CHART_AXIS.labelMarkerRadius}
            className={styles.labelMarker}
            data-trend-label-marker={coord.point.date}
          />
        ))}
        <rect
          x={VERIFIED_REVENUE_CHART_PAD.left}
          y={VERIFIED_REVENUE_CHART_PAD.top}
          width={plotW}
          height={plotH}
          className={styles.plotHitArea}
          data-plot-hit-area
          onPointerMove={handlePlotPointerMove}
          onPointerLeave={handlePlotPointerLeave}
        />
        {coords.map((coord, index) => (
          <circle
            key={`${coord.point.date}-${coord.point.status}`}
            cx={coord.x}
            cy={coord.y}
            r={
              coord.point.status === 'zero' || activeIndex === index
                ? VERIFIED_REVENUE_CHART_AXIS.activePointRadius
                : coord.point.status === 'unavailable'
                  ? 0
                  : 0
            }
            className={[
              styles.point,
              coord.point.status === 'zero' ? styles.zeroPoint : '',
            ].join(' ')}
            strokeWidth={VERIFIED_REVENUE_CHART_AXIS.lineStrokeWidth}
            onFocus={() => handlePointFocus(index)}
            onBlur={() => {
              setFocusedIndex(null);
              setHover(null);
            }}
            onClick={() => handlePointActivate(coord.point)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                handlePointActivate(coord.point);
              }
            }}
            tabIndex={coord.point.status === 'unavailable' ? -1 : 0}
            role={coord.point.status === 'unavailable' ? undefined : 'button'}
            aria-label={
              coord.point.status === 'unavailable'
                ? undefined
                : `Open claims ledger for ${coord.point.date} snapshot window`
            }
            aria-describedby={activeIndex === index ? tooltipId : undefined}
            data-trend-point={coord.point.date}
            data-trend-point-status={coord.point.status}
          />
        ))}
        </g>
        {gapMarkers.map((marker) => {
          const labelLayout = resolveGapLabelLayout(marker);
          return (
            <g
              key={`gap-${marker.point.date}`}
              data-trend-gap-marker={marker.point.date}
              aria-hidden="true"
            >
              <circle
                cx={marker.x}
                cy={marker.y}
                r={VERIFIED_REVENUE_CHART_AXIS.activePointRadius}
                className={styles.gapMarker}
              />
              <text
                x={marker.x + labelLayout.dx}
                y={labelLayout.labelY}
                className={styles.gapLabel}
                fontSize={VERIFIED_REVENUE_CHART_AXIS.gapLabelFontSize}
                textAnchor={labelLayout.textAnchor}
                dominantBaseline="auto"
              >
                {COMMAND_CENTER_COPY.trendDataUnavailableChartLabel}
              </text>
            </g>
          );
        })}
        {xLabels.map((label) => (
          <text
            key={label.date}
            x={label.x}
            y={label.labelY}
            className={styles.axisLabel}
            fontSize={VERIFIED_REVENUE_CHART_AXIS.xLabelFontSize}
            textAnchor={label.textAnchor}
            dominantBaseline="hanging"
            data-trend-x-axis-label={label.date}
          >
            {label.label}
          </text>
        ))}
      </svg>
      {active && hover && tooltipContent ? (
        <div
          id={tooltipId}
          className={[
            styles.tooltip,
            hover.placement === 'below' ? styles.tooltipBelow : styles.tooltipAbove,
          ].join(' ')}
          role="tooltip"
          style={{ left: `${hover.tooltipLeft}px`, top: `${hover.tooltipTop}px` }}
          data-trend-tooltip
        >
          {active.point.status === 'unavailable' ? (
            <>
              <p className={styles.tooltipPrimary}>{COMMAND_CENTER_COPY.trendDataUnavailableLabel}</p>
              {active.point.unavailableReason ? (
                <p className={styles.tooltipMeta}>{active.point.unavailableReason}</p>
              ) : null}
            </>
          ) : (
            <>
              <p className={styles.tooltipMeta}>{tooltipContent.dateLabel}</p>
              <p className={styles.tooltipPrimary}>{tooltipContent.primaryValue}</p>
            </>
          )}
        </div>
      ) : null}
      <span id={liveRegionId} className={styles.srOnly} aria-live="polite">
        {liveSummary}
      </span>
    </div>
  );
}
