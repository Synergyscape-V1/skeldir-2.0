import React, { useMemo } from "react";
import type { ComparisonChannelData } from "../../../types/comparison";
import { displayChannelName, platformMeta } from "../../core/constants";

interface ClarityConfidenceStripProps {
  channels: ComparisonChannelData[];
}

function toPercent(value: number, min: number, max: number): number {
  if (max <= min) return 0;
  return ((value - min) / (max - min)) * 100;
}

export function ClarityConfidenceStrip({ channels }: ClarityConfidenceStripProps) {
  const min = useMemo(
    () => Math.min(...channels.map((c) => c.confidenceRange.low)) - 0.2,
    [channels]
  );
  const max = useMemo(
    () => Math.max(...channels.map((c) => c.confidenceRange.high)) + 0.2,
    [channels]
  );

  const rangesOverlap = useMemo(() => {
    if (channels.length < 2) return false;
    const sorted = [...channels].sort((a, b) => b.performance.roas - a.performance.roas);
    return sorted[0].confidenceRange.low <= sorted[1].confidenceRange.high;
  }, [channels]);

  return (
    <div className="cc-a-conf-strip" role="figure" aria-label="ROAS confidence ranges">
      {channels.map((channel) => {
        const meta = platformMeta(channel.channel.platform_type);
        const name = displayChannelName(channel.channel.name, channel.channel.platform_type);
        const low = toPercent(channel.confidenceRange.low, min, max);
        const high = toPercent(channel.confidenceRange.high, min, max);
        const marker = toPercent(channel.performance.roas, min, max);

        return (
          <div key={channel.channel.id} className="cc-a-conf-row">
            <span className="cc-a-conf-label">
              <img src={meta.iconSrc} alt={meta.label} width={20} height={20} />
              {name}
            </span>
            <div className={`cc-a-conf-track cc-a-conf-tier-${channel.confidenceRange.level}`}>
              <span
                className="cc-a-conf-range"
                style={{ left: `${low}%`, width: `${Math.max(2, high - low)}%` }}
              />
              <span className="cc-a-conf-marker" style={{ left: `${marker}%` }} />
            </div>
            <span className="cc-a-conf-value">
              {channel.confidenceRange.low.toFixed(2)}–{channel.confidenceRange.high.toFixed(2)}
            </span>
          </div>
        );
      })}
      <p className="cc-a-conf-annotation">
        {rangesOverlap
          ? "Confidence ranges overlap \u2014 no statistically reliable winner."
          : "Ranges do not overlap \u2014 winner is statistically reliable."}
      </p>
    </div>
  );
}
