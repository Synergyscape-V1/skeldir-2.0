import React from "react";
import type { ChannelComparisonRendererProps } from "../../../types/comparison";
import type { ComparisonChannelData } from "../../../types/comparison";
import type { DateRangeValue } from "../../../types/channel";
import {
  ChannelCards,
  ConfidenceRangeFigure,
  SynchronizedRevenueChart,
} from "../../components";

interface EvidenceAccordionProps {
  state: ChannelComparisonRendererProps["state"];
  loadedChannels: ComparisonChannelData[];
  dateRange: DateRangeValue;
  onRemoveChannel: (channelId: string) => void;
  onRetryChannel: (channelId: string) => void;
}

export function EvidenceAccordion({
  state,
  loadedChannels,
  dateRange,
  onRemoveChannel,
  onRetryChannel,
}: EvidenceAccordionProps) {
  const channelCount = loadedChannels.length;
  const best = channelCount > 0
    ? [...loadedChannels].sort((a, b) => b.performance.roas - a.performance.roas)[0]
    : null;
  const hasMultiple = channelCount >= 2;

  return (
    <div className="cc-d-evidence">
      <details className="cc-d-evidence-section" open>
        <summary>
          <span className="cc-d-evidence-title">Channel Performance</span>
          <span className="cc-d-evidence-summary">
            {channelCount} channel{channelCount !== 1 ? "s" : ""} compared
            {best ? `, ${best.channel.name} leads ROAS` : ""}
          </span>
        </summary>
        <div className="cc-d-evidence-body">
          <ChannelCards
            state={state}
            onRemoveChannel={onRemoveChannel}
            onRetryChannel={onRetryChannel}
          />
        </div>
      </details>

      {hasMultiple ? (
        <details className="cc-d-evidence-section" open>
          <summary>
            <span className="cc-d-evidence-title">Confidence Analysis</span>
            <span className="cc-d-evidence-summary">
              ROAS confidence ranges for {channelCount} channels
            </span>
          </summary>
          <div className="cc-d-evidence-body">
            <ConfidenceRangeFigure channels={loadedChannels} />
          </div>
        </details>
      ) : null}

      {hasMultiple ? (
        <details className="cc-d-evidence-section" open>
          <summary>
            <span className="cc-d-evidence-title">Revenue Trends</span>
            <span className="cc-d-evidence-summary">
              Historical revenue comparison
            </span>
          </summary>
          <div className="cc-d-evidence-body">
            <SynchronizedRevenueChart channels={loadedChannels} dateRange={dateRange} />
          </div>
        </details>
      ) : null}
    </div>
  );
}
