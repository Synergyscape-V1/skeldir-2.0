import React, { useState } from "react";
import "../../command-center/command-center.css";

export function HealthScoreBanner({
  score = 74,
  threshold = 70,
  timestamp = "09:14:22",
  onViewBreakdown,
}: {
  score?: number;
  threshold?: number;
  timestamp?: string;
  onViewBreakdown?: () => void;
}) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const belowThreshold = score <= threshold;
  const critical = belowThreshold;

  return (
    <div
      className={`cc-rev-disc-banner cc-rev-disc-banner--${critical ? "critical" : "caution"}`}
      role="region"
      aria-label="Data health score alert"
    >
      <div className="cc-rev-disc-banner__top">
        <div className="cc-rev-disc-banner__body">
          <p className="cc-rev-disc-banner__text">
            Data Health needs review.{' '}
            <strong className="cc-rev-disc-banner__disc" title="Composite score threshold for review">
              Threshold ≤{threshold}/100
            </strong>
            .{' '}
            Current score:{' '}
            <span className="cc-rev-disc-banner__amount">{score}/100</span>
            .
            {belowThreshold && (
              <>
                {' '}
                <span className="cc-rev-disc-banner__severe">Below threshold — review urgently.</span>
              </>
            )}
          </p>
          <div className="cc-rev-disc-banner__subrow">
            <p className="cc-rev-disc-banner__meta">As of {timestamp}</p>
            <button type="button" className="cc-rev-disc-banner__link" onClick={() => onViewBreakdown?.()}>
              View breakdown →
            </button>
          </div>
        </div>
        <button
          type="button"
          className="cc-rev-disc-banner__dismiss"
          aria-label="Dismiss alert for this session"
          onClick={() => setDismissed(true)}
        >
          ×
        </button>
      </div>
    </div>
  );
}
