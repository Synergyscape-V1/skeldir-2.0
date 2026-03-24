import type { ComparisonChannelData } from "../../types/comparison";
import type { PlatformType } from "../../types/channel";
import { ChannelIcon } from "./ChannelIcon";
import { displayChannelName } from "../core/constants";

interface ConfidenceChartProps {
  channels: ComparisonChannelData[];
}

const CHART_COLORS: Record<string, { bg: string; mid: string; midBg: string }> = {
  ch_google_ads: {
    bg: "var(--dc-chart-google-faint)",
    mid: "var(--dc-chart-google)",
    midBg: "hsla(171, 66%, 45%, 0.15)",
  },
  ch_facebook_ads: {
    bg: "var(--dc-chart-meta-faint)",
    mid: "var(--dc-chart-meta)",
    midBg: "hsla(142, 55%, 49%, 0.15)",
  },
  ch_pinterest_ads: {
    bg: "var(--dc-chart-pinterest-faint)",
    mid: "var(--dc-chart-pinterest)",
    midBg: "hsla(45, 93%, 58%, 0.15)",
  },
  ch_tiktok_ads: {
    bg: "var(--dc-chart-tiktok-faint)",
    mid: "var(--dc-chart-tiktok)",
    midBg: "hsla(0, 0%, 20%, 0.15)",
  },
};

function getColors(channelId: string) {
  return CHART_COLORS[channelId] ?? CHART_COLORS.ch_google_ads;
}

function shortName(name: string, _platformType: PlatformType): string {
  const display = displayChannelName(name, _platformType);
  return display.split(" ")[0];
}

function buildInsightText(channels: ComparisonChannelData[]): string {
  if (channels.length < 2) return "";
  const sorted = [...channels].sort((a, b) => b.performance.roas - a.performance.roas);
  const best = sorted[0];
  const worst = sorted[sorted.length - 1];
  const bestName = displayChannelName(best.channel.name, best.channel.platform_type);
  const worstName = displayChannelName(worst.channel.name, worst.channel.platform_type);
  const bestRange = best.confidenceRange;
  const worstRange = worst.confidenceRange;
  const bestWidth = (bestRange.high - bestRange.low).toFixed(2);
  const worstWidth = (worstRange.high - worstRange.low).toFixed(2);
  const bestTight = bestRange.high - bestRange.low < 1;

  return `${bestName}'s ${bestTight ? "tight, high" : "high"} range (${bestRange.low.toFixed(2)}-${bestRange.high.toFixed(2)}) indicates reliable outperformance compared to ${worstName}'s ${worstWidth > bestWidth ? "wide, uncertain" : "wider"} range (${worstRange.low.toFixed(2)}-${worstRange.high.toFixed(2)}).`;
}

export function ConfidenceChart({ channels }: ConfidenceChartProps) {
  if (channels.length === 0) return null;

  // Compute axis bounds
  const allLows = channels.map((c) => c.confidenceRange.low);
  const allHighs = channels.map((c) => c.confidenceRange.high);
  const dataMin = Math.min(...allLows);
  const dataMax = Math.max(...allHighs);

  const minVal = Math.floor(dataMin * 2) / 2;
  const maxVal = Math.ceil(dataMax * 2) / 2 + 0.5;
  const range = maxVal - minVal;

  const toPercent = (val: number) => ((val - minVal) / range) * 100;

  // Generate tick marks
  const ticks: number[] = [];
  for (let t = minVal; t <= maxVal; t = Math.round((t + 0.5) * 10) / 10) {
    ticks.push(t);
  }

  const insightText = buildInsightText(channels);

  return (
    <div className="dc-confidence-card">
      <h3 className="dc-confidence-title">ROAS confidence ranges by channel</h3>

      <div className="dc-confidence-layout">
        {/* Chart area */}
        <div className="dc-confidence-chart-area">
          <div className="dc-confidence-chart-inner">
            {/* Vertical grid lines */}
            {ticks.map((t) => (
              <div
                key={t}
                className="dc-confidence-gridline"
                style={{ left: `${toPercent(t)}%` }}
              />
            ))}

            {/* Rows */}
            <div className="dc-confidence-rows">
              {channels.map((ch) => {
                const low = ch.confidenceRange.low;
                const high = ch.confidenceRange.high;
                const mid = ch.performance.roas;
                const leftPct = toPercent(low);
                const widthPct = toPercent(high) - leftPct;
                const colors = getColors(ch.channel.id);

                return (
                  <div key={ch.channel.id} className="dc-confidence-row">
                    {/* Label */}
                    <div className="dc-confidence-row-label">
                      <ChannelIcon platformType={ch.channel.platform_type} size={18} />
                      <span className="dc-confidence-row-label-text">
                        {shortName(ch.channel.name, ch.channel.platform_type)}
                      </span>
                    </div>

                    {/* Bar area */}
                    <div className="dc-confidence-bar-area">
                      {/* Range bar with mid value centered as plain text */}
                      <div
                        className="dc-confidence-range-bar"
                        style={{
                          left: `${leftPct}%`,
                          width: `${widthPct}%`,
                          background: colors.bg,
                        }}
                      >
                        <span
                          className="dc-confidence-label dc-confidence-label-mid"
                          style={undefined}
                        >
                          {mid.toFixed(2)}
                        </span>
                      </div>

                      {/* Low label */}
                      <span
                        className="dc-confidence-label dc-confidence-label-low"
                        style={{ left: `${leftPct}%` }}
                      >
                        {low.toFixed(2)}
                      </span>

                      {/* High label */}
                      <span
                        className="dc-confidence-label dc-confidence-label-high"
                        style={{ left: `${toPercent(high)}%` }}
                      >
                        {high.toFixed(2)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Baseline */}
            <div className="dc-confidence-baseline" />

            {/* X-axis */}
            <div className="dc-confidence-xaxis">
              {ticks.map((t) => (
                <span
                  key={t}
                  className="dc-confidence-tick-label"
                  style={{ left: `${toPercent(t)}%` }}
                >
                  {t.toFixed(1)}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Insight sidebar */}
        {insightText && (
          <div className="dc-confidence-insight">
            <h4>Why this matters:</h4>
            <p>{insightText}</p>
          </div>
        )}
      </div>
    </div>
  );
}
