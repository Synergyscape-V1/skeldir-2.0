import React, { useMemo } from "react";
import type { ComparisonChannelData, WinnerDeclaration } from "../../types/comparison";
import { displayChannelName, platformMeta } from "../core/constants";

interface ConfidenceRangeFigureProps {
  channels: ComparisonChannelData[];
  winner?: WinnerDeclaration | null;
  title?: string;
}

function toPercent(value: number, min: number, max: number): number {
  if (max <= min) return 0;
  return ((value - min) / (max - min)) * 100;
}

export function ConfidenceRangeFigure({
  channels,
  winner,
  title = "ROAS confidence ranges by channel",
}: ConfidenceRangeFigureProps) {
  const min = useMemo(() => {
    const lowest = Math.min(...channels.map((c) => c.confidenceRange.low));
    return Math.max(0, Math.floor((lowest - 0.5) * 2) / 2);
  }, [channels]);

  const max = useMemo(() => {
    const highest = Math.max(...channels.map((c) => c.confidenceRange.high));
    return Math.ceil((highest + 0.5) * 2) / 2;
  }, [channels]);

  const ticks = useMemo(() => {
    const step = 0.5;
    const result: number[] = [];
    for (let v = min; v <= max + 0.01; v += step) {
      result.push(Number(v.toFixed(1)));
    }
    return result;
  }, [min, max]);

  const winnerChannel = winner
    ? channels.find((c) => c.channel.id === winner.channelId)
    : null;
  const runnerUp = winner
    ? [...channels].sort((a, b) => b.performance.roas - a.performance.roas).find((c) => c.channel.id !== winner.channelId)
    : null;

  const annotationText = useMemo(() => {
    if (!winnerChannel || !runnerUp) return null;
    const winnerName = displayChannelName(winnerChannel.channel.name, winnerChannel.channel.platform_type);
    const loserName = displayChannelName(runnerUp.channel.name, runnerUp.channel.platform_type);
    return `${winnerName}'s tight, high range (${winnerChannel.confidenceRange.low.toFixed(2)}-${winnerChannel.confidenceRange.high.toFixed(2)}) indicates reliable outperformance compared to ${loserName}'s wide, uncertain range (${runnerUp.confidenceRange.low.toFixed(2)}-${runnerUp.confidenceRange.high.toFixed(2)}).`;
  }, [winnerChannel, runnerUp]);

  return (
    <figure
      className="cc-confidence-figure"
      role="figure"
      aria-label={`ROAS confidence range comparison chart for ${channels.map((c) => c.channel.name).join(", ")}`}
    >
      <figcaption>{title}</figcaption>

      <div className="cc-confidence-layout">
        <div className="cc-confidence-chart">
          <div className="cc-confidence-rows">
            {/* Dashed grid lines */}
            <div className="cc-confidence-grid" aria-hidden="true">
              {ticks.map((tick) => (
                <span
                  key={tick}
                  className="cc-confidence-gridline"
                  style={{ left: `${toPercent(tick, min, max)}%` }}
                />
              ))}
            </div>

            {channels.map((channel) => {
              const meta = platformMeta(channel.channel.platform_type);
              const name = displayChannelName(channel.channel.name, channel.channel.platform_type);
              const low = toPercent(channel.confidenceRange.low, min, max);
              const high = toPercent(channel.confidenceRange.high, min, max);
              const marker = toPercent(channel.performance.roas, min, max);
              const tier = channel.confidenceRange.level;

              return (
                <div key={channel.channel.id} className="cc-confidence-row">
                  <div className="cc-confidence-label">
                    <img src={meta.iconSrc} alt={meta.label} width={20} height={20} />
                    <span>{name}</span>
                  </div>
                  <div className="cc-confidence-track-wrap">
                    <div className={`cc-confidence-track confidence-${tier}`}>
                      <span
                        className="cc-confidence-range"
                        style={{ left: `${low}%`, width: `${Math.max(2, high - low)}%` }}
                      />
                      <span className="cc-confidence-marker" style={{ left: `${marker}%` }} />
                    </div>
                    {/* Inline value labels */}
                    <div className="cc-confidence-values">
                      <span className="cc-confidence-val-low" style={{ left: `${low}%` }}>
                        {channel.confidenceRange.low.toFixed(2)}
                      </span>
                      <span className="cc-confidence-val-roas" style={{ left: `${marker}%` }}>
                        {channel.performance.roas.toFixed(2)}
                      </span>
                      <span className="cc-confidence-val-high" style={{ left: `${high}%` }}>
                        {channel.confidenceRange.high.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Bottom axis */}
          <div className="cc-confidence-axis">
            {ticks.map((tick) => (
              <span key={tick} style={{ left: `${toPercent(tick, min, max)}%` }}>
                {tick.toFixed(1)}
              </span>
            ))}
          </div>
        </div>

        {/* Why this matters annotation */}
        {annotationText ? (
          <aside className="cc-confidence-annotation">
            <h4>Why this matters:</h4>
            <p>{annotationText}</p>
          </aside>
        ) : null}
      </div>
    </figure>
  );
}
