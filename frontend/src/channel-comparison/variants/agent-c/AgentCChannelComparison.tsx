import React from "react";
import type { ChannelComparisonRendererProps } from "../../../types/comparison";
import {
  EmptyComparisonState,
  GlobalErrorBanner,
  SynchronizedRevenueChart,
} from "../../components";
import { ConfidenceHeroBanner } from "./ConfidenceHeroBanner";
import { ConfidenceTierCards } from "./ConfidenceTierCards";
import { ConfidenceAwareBudgetBanner } from "./ConfidenceAwareBudgetBanner";
import "./styles.css";

export function AgentCChannelComparison({
  state,
  onRetryGlobal,
}: ChannelComparisonRendererProps) {
  const loadedChannels = state.selectedChannelIds
    .map((id) => state.channelData[id])
    .filter(Boolean);

  const hasChannels = state.selectedChannelIds.length > 0;
  const hasMultiple = loadedChannels.length >= 2;
  const anyLoading = state.selectedChannelIds.some((id) => state.loading[id]);

  return (
    <section className="cc-agent cc-agent-c" aria-label="Confidence as Hero — Channel Comparison">
      {state.availableChannelsError ? (
        <GlobalErrorBanner error={state.availableChannelsError} onRetry={onRetryGlobal} />
      ) : null}

      {!hasChannels ? <EmptyComparisonState /> : null}

      {hasChannels && anyLoading ? (
        <div className="cc-c-loading" aria-busy="true">
          <div className="cc-skeleton-line wide" />
          <div className="cc-skeleton-line short" />
          <div className="cc-skeleton-line wide" />
          <div className="cc-skeleton-line short" />
        </div>
      ) : null}

      {hasChannels && !anyLoading ? (
        <div className="cc-c-content">
          {hasMultiple ? (
            <ConfidenceHeroBanner channels={loadedChannels} winner={state.winner} />
          ) : null}

          <ConfidenceTierCards
            channels={loadedChannels}
            derivedByChannelId={state.derivedByChannelId}
          />

          {hasMultiple ? (
            <SynchronizedRevenueChart channels={loadedChannels} dateRange={state.dateRange} />
          ) : null}

          <ConfidenceAwareBudgetBanner recommendation={state.budgetRecommendation} />
        </div>
      ) : null}
    </section>
  );
}
