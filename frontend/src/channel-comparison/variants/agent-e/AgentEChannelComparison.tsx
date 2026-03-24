import React from "react";
import type { ChannelComparisonRendererProps } from "../../../types/comparison";
import {
  BudgetRecommendationBanner,
  ChannelCards,
  ConfidenceRangeFigure,
  DenseMatrix,
  EmptyComparisonState,
  GlobalErrorBanner,
  ModelRecommendationPanel,
  SynchronizedRevenueChart,
  WinnerBanner,
} from "../../components";
import "./styles.css";

export function AgentEChannelComparison({
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
    <section className="cc-agent cc-agent-e" aria-label="Canonical Fidelity — Channel Comparison">
      {state.availableChannelsError ? (
        <GlobalErrorBanner error={state.availableChannelsError} onRetry={onRetryGlobal} />
      ) : null}

      {!hasChannels ? <EmptyComparisonState /> : null}

      {hasChannels ? (
        <div className="cc-e-content">
          {/* 1. Budget recommendation banner at top */}
          <BudgetRecommendationBanner recommendation={state.budgetRecommendation} />

          {/* 2. KPI hero cards */}
          <ChannelCards
            state={state}
            className="cc-e-cards"
            onRemoveChannel={onRemoveChannel}
            onRetryChannel={onRetryChannel}
          />

          {hasMultiple ? (
            <>
              {/* 3. Confidence range figure with annotation */}
              <ConfidenceRangeFigure
                channels={loadedChannels}
                winner={state.winner}
                title="ROAS confidence ranges by channel"
              />

              {/* 4. Table + Model recommendation side panel */}
              <div className="cc-grid-two">
                <DenseMatrix state={state} />
                <ModelRecommendationPanel
                  recommendation={state.budgetRecommendation}
                  winnerName={state.winner?.channelName}
                />
              </div>

              {/* 5. Revenue trend chart */}
              <SynchronizedRevenueChart
                channels={loadedChannels}
                dateRange={state.dateRange}
              />
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
