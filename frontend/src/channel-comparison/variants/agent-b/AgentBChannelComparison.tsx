import React from "react";
import type { ChannelComparisonRendererProps } from "../../../types/comparison";
import {
  BudgetRecommendationBanner,
  EmptyComparisonState,
  GlobalErrorBanner,
  SynchronizedRevenueChart,
  WinnerBanner,
} from "../../components";
import { DenseComparisonTable } from "./DenseComparisonTable";
import { CompactConfidenceOverlay } from "./CompactConfidenceOverlay";
import "./styles.css";

export function AgentBChannelComparison({
  state,
  onRemoveChannel,
  onRetryChannel,
  onRetryGlobal,
}: ChannelComparisonRendererProps) {
  const loadedChannels = state.selectedChannelIds
    .map((id) => state.channelData[id])
    .filter(Boolean);

  const hasChannels = state.selectedChannelIds.length > 0;
  const hasMultiple = loadedChannels.length >= 2;

  return (
    <section className="cc-agent cc-agent-b" aria-label="Data Density — Channel Comparison">
      {state.availableChannelsError ? (
        <GlobalErrorBanner error={state.availableChannelsError} onRetry={onRetryGlobal} />
      ) : null}

      {!hasChannels ? <EmptyComparisonState /> : null}

      {hasChannels ? (
        <div className="cc-b-content">
          <WinnerBanner winner={state.winner} channels={loadedChannels} />

          <DenseComparisonTable
            state={state}
            onRemoveChannel={onRemoveChannel}
            onRetryChannel={onRetryChannel}
          />

          {hasMultiple ? (
            <>
              <CompactConfidenceOverlay channels={loadedChannels} />
              <SynchronizedRevenueChart channels={loadedChannels} dateRange={state.dateRange} />
            </>
          ) : null}

          <BudgetRecommendationBanner recommendation={state.budgetRecommendation} />
        </div>
      ) : null}
    </section>
  );
}
