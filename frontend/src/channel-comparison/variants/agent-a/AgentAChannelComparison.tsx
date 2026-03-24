import React from "react";
import type { ChannelComparisonRendererProps } from "../../../types/comparison";
import {
  BudgetRecommendationBanner,
  EmptyComparisonState,
  GlobalErrorBanner,
  SynchronizedRevenueChart,
  WinnerBanner,
} from "../../components";
import { ClarityHeroMetrics } from "./ClarityHeroMetrics";
import { ClarityConfidenceStrip } from "./ClarityConfidenceStrip";
import "./styles.css";

export function AgentAChannelComparison({
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
    <section className="cc-agent cc-agent-a" aria-label="Clarity First — Channel Comparison">
      {state.availableChannelsError ? (
        <GlobalErrorBanner error={state.availableChannelsError} onRetry={onRetryGlobal} />
      ) : null}

      {!hasChannels ? <EmptyComparisonState /> : null}

      {hasChannels ? (
        <div className="cc-a-content">
          <ClarityHeroMetrics
            state={state}
            onRemoveChannel={onRemoveChannel}
            onRetryChannel={onRetryChannel}
          />

          <WinnerBanner winner={state.winner} channels={loadedChannels} />

          {hasMultiple ? (
            <>
              <ClarityConfidenceStrip channels={loadedChannels} />
              <SynchronizedRevenueChart channels={loadedChannels} dateRange={state.dateRange} />
            </>
          ) : null}

          <BudgetRecommendationBanner recommendation={state.budgetRecommendation} />
        </div>
      ) : null}
    </section>
  );
}
