import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import type { ChannelInlineTrendPoint } from '../../../channels/channelInlineFixtures';
import { CHANNEL_INLINE_COPY } from '../../../channels/channelInlineCopy';
import {
  channelTrendBarHeightPct,
  channelTrendDeltaVsPrior,
  channelTrendMaxMinor,
  channelTrendPeriodLabel,
  channelTrendYTicks,
} from '../../../channels/channelVerifiedTrend';
import { formatMoneyMinorDisplay } from '../../../lib/money';
import shared from '../../../styles/shared.module.css';
import styles from './ChannelVerifiedTrendBars.module.css';

export type ChannelVerifiedTrendBarsState = 'default' | 'loading' | 'empty' | 'error';

export interface ChannelVerifiedTrendBarsProps {
  points: ChannelInlineTrendPoint[];
  currencyCode: string;
  state?: ChannelVerifiedTrendBarsState;
  onRetry?: () => void;
}

const SKELETON_HEIGHTS = [40, 65, 55, 80];

function AxisFrame({
  yTicks,
  children,
  showMidGuide,
  skeleton,
}: {
  yTicks: Array<{ key: string; label: string }>;
  children: ReactNode;
  showMidGuide: boolean;
  skeleton?: boolean;
}) {
  return (
    <div className={styles.chartFrame} data-channel-trend-axes>
      <div className={styles.yAxis} data-channel-trend-y-axis aria-hidden={skeleton || undefined}>
        <div className={styles.ySpine} />
        {yTicks.map((tick) => (
          <span
            key={tick.key}
            className={[
              styles.yTick,
              tick.key === 'max' ? styles.yTickMax : '',
              tick.key === 'mid' ? styles.yTickMid : '',
              tick.key === 'zero' ? styles.yTickZero : '',
              skeleton ? styles.yTickSkeleton : '',
            ]
              .filter(Boolean)
              .join(' ')}
            data-channel-trend-y-tick={tick.key}
          >
            {skeleton ? null : tick.label}
          </span>
        ))}
      </div>
      <div className={styles.plotPane}>
        {showMidGuide ? <div className={styles.guide} aria-hidden /> : null}
        <div className={styles.xSpine} aria-hidden />
        {children}
      </div>
    </div>
  );
}

export function ChannelVerifiedTrendBars({
  points,
  currencyCode,
  state: stateProp,
  onRetry,
}: ChannelVerifiedTrendBarsProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const liveRegionId = useId();
  /** Spotlighted period for the anchored readout (hover or keyboard focus) — never overlays bars. */
  const [spotlightIndex, setSpotlightIndex] = useState<number | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [focusIndex, setFocusIndex] = useState(0);

  const resolvedState: ChannelVerifiedTrendBarsState =
    stateProp ?? (points.length === 0 ? 'empty' : 'default');

  if (resolvedState === 'loading') {
    return (
      <div
        className={styles.wrap}
        data-channel-inline-trend
        data-channel-trend-state="loading"
        aria-busy="true"
        aria-label={CHANNEL_INLINE_COPY.trend.sectionLabel}
      >
        <div className={styles.cluster}>
          <AxisFrame
            skeleton
            showMidGuide
            yTicks={[
              { key: 'max', label: '' },
              { key: 'mid', label: '' },
              { key: 'zero', label: '' },
            ]}
          >
            <ul className={styles.columns} aria-hidden>
              {SKELETON_HEIGHTS.map((height, index) => (
                <li key={index} className={styles.column}>
                  <div className={styles.hit}>
                    <span className={styles.skeletonBar} style={{ height: `${height}%` }} />
                  </div>
                  <span className={styles.skeletonLabel} />
                </li>
              ))}
            </ul>
          </AxisFrame>
        </div>
      </div>
    );
  }

  if (resolvedState === 'error') {
    return (
      <div
        className={styles.wrap}
        data-channel-inline-trend
        data-channel-trend-state="error"
        role="alert"
      >
        <div className={styles.emptyPlot}>
          <div className={[styles.xSpine, styles.baselineDashed].join(' ')} />
          <p className={styles.stateCopy}>{CHANNEL_INLINE_COPY.trend.error}</p>
          {onRetry ? (
            <button
              type="button"
              className={[styles.retry, shared.focusVisible].join(' ')}
              onClick={onRetry}
              data-channel-trend-retry
            >
              {CHANNEL_INLINE_COPY.trend.retry}
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  if (resolvedState === 'empty' || points.length === 0) {
    return (
      <div
        className={styles.wrap}
        data-channel-inline-trend
        data-channel-trend-state="empty"
        data-channel-inline-trend-empty
      >
        <div className={styles.emptyPlot}>
          <div className={[styles.xSpine, styles.baselineDashed].join(' ')} />
          <p className={styles.stateCopy}>{CHANNEL_INLINE_COPY.trend.empty}</p>
        </div>
      </div>
    );
  }

  const maxMinor = channelTrendMaxMinor(points);
  const yTicks = channelTrendYTicks(maxMinor).map((tick) => ({
    key: tick.key,
    label: formatMoneyMinorDisplay(tick.valueMinor, currencyCode),
  }));
  const lastIndex = points.length - 1;
  const lastPoint = points[lastIndex]!;
  const priorPoint = lastIndex > 0 ? points[lastIndex - 1]! : null;
  const latestDelta = channelTrendDeltaVsPrior(
    lastPoint.verifiedRevenueMinor,
    priorPoint ? priorPoint.verifiedRevenueMinor : null,
  );
  const spotlightPoint = spotlightIndex != null ? points[spotlightIndex] : null;
  const spotlightDelta =
    spotlightIndex != null && spotlightIndex > 0
      ? channelTrendDeltaVsPrior(
          points[spotlightIndex]!.verifiedRevenueMinor,
          points[spotlightIndex - 1]!.verifiedRevenueMinor,
        )
      : null;
  const maxDisplay = formatMoneyMinorDisplay(maxMinor, currencyCode);
  const plotSummary = `${CHANNEL_INLINE_COPY.trend.sectionLabel}. Scale 0 to ${maxDisplay} by week.`;
  const announce = spotlightPoint
    ? `${channelTrendPeriodLabel(spotlightPoint.period)}: ${formatMoneyMinorDisplay(
        spotlightPoint.verifiedRevenueMinor,
        currencyCode,
      )}`
    : '';

  const onBarKeyDown = (event: KeyboardEvent, index: number) => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      const next = Math.min(points.length - 1, index + 1);
      setFocusIndex(next);
      setSpotlightIndex(next);
      const btn = wrapRef.current?.querySelector<HTMLButtonElement>(
        `[data-channel-trend-bar="${next}"]`,
      );
      btn?.focus();
      return;
    }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      const next = Math.max(0, index - 1);
      setFocusIndex(next);
      setSpotlightIndex(next);
      const btn = wrapRef.current?.querySelector<HTMLButtonElement>(
        `[data-channel-trend-bar="${next}"]`,
      );
      btn?.focus();
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setSelectedIndex((current) => (current === index ? null : index));
    }
  };

  return (
    <div
      ref={wrapRef}
      className={styles.wrap}
      data-channel-inline-trend
      data-channel-trend-state="default"
      data-channel-trend-point-count={points.length}
    >
      <div className={styles.cluster}>
        <div className={styles.metaRow}>
          {spotlightPoint ? (
            <div
              className={styles.hoverReadout}
              role="tooltip"
              data-channel-trend-tooltip
              data-channel-trend-readout
            >
              <span className={styles.hoverPeriod}>
                {channelTrendPeriodLabel(spotlightPoint.period)}
              </span>
              <span className={styles.hoverValue}>
                {formatMoneyMinorDisplay(spotlightPoint.verifiedRevenueMinor, currencyCode)}
              </span>
              {spotlightDelta ? (
                <span className={styles.hoverDelta}>{spotlightDelta.label}</span>
              ) : null}
            </div>
          ) : (
            <span
              className={[
                styles.deltaChip,
                latestDelta.tone === 'success'
                  ? styles.deltaSuccess
                  : latestDelta.tone === 'error'
                    ? styles.deltaError
                    : styles.deltaNeutral,
              ].join(' ')}
              data-channel-trend-delta
              data-channel-trend-delta-tone={latestDelta.tone}
            >
              {latestDelta.label}
            </span>
          )}
        </div>

        <AxisFrame yTicks={yTicks} showMidGuide={maxMinor > 0n}>
          <div
            className={styles.plot}
            role="img"
            aria-label={plotSummary}
            data-channel-trend-x-axis
          >
            <ul className={styles.columns} role="list">
              {points.map((point, index) => {
                const heightPct = channelTrendBarHeightPct(point.verifiedRevenueMinor, maxMinor);
                const isZero = point.verifiedRevenueMinor <= 0n;
                const display = formatMoneyMinorDisplay(point.verifiedRevenueMinor, currencyCode);
                const periodLabel = channelTrendPeriodLabel(point.period);
                const isLatest = index === lastIndex;
                const isSelected = selectedIndex === index;
                const isSpotlighted = spotlightIndex === index;
                return (
                  <li key={point.period} className={styles.column} data-channel-trend-period={point.period}>
                    <button
                      type="button"
                      className={[styles.hit, shared.focusVisible].join(' ')}
                      data-channel-trend-bar={index}
                      tabIndex={focusIndex === index ? 0 : -1}
                      aria-label={`${periodLabel}: ${display}`}
                      aria-pressed={isSelected}
                      onPointerEnter={() => setSpotlightIndex(index)}
                      onPointerLeave={() => setSpotlightIndex(null)}
                      onFocus={() => {
                        setFocusIndex(index);
                        setSpotlightIndex(index);
                      }}
                      onBlur={(event) => {
                        const next = event.relatedTarget as Node | null;
                        if (!wrapRef.current?.contains(next)) {
                          setSpotlightIndex(null);
                        }
                      }}
                      onClick={() => setSelectedIndex((current) => (current === index ? null : index))}
                      onKeyDown={(event) => onBarKeyDown(event, index)}
                    >
                      <span
                        className={[
                          styles.bar,
                          isZero ? styles.barHairline : '',
                          isLatest ? styles.barLatest : styles.barPrior,
                          isSpotlighted || isSelected ? styles.barActive : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                        style={isZero ? undefined : { height: `${heightPct}%` }}
                        aria-hidden
                      />
                    </button>
                    <span
                      className={[styles.xTick, isSelected ? styles.xTickSelected : ''].join(' ')}
                      data-channel-trend-x-tick={point.period}
                    >
                      {periodLabel}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        </AxisFrame>
      </div>

      <span id={liveRegionId} className={shared.srOnly} aria-live="polite">
        {announce}
      </span>
    </div>
  );
}
