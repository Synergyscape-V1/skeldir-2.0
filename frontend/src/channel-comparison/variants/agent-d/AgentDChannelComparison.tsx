import React, { useRef } from "react";
import type { ChannelComparisonRendererProps } from "../../../types/comparison";
import {
  EmptyComparisonState,
  GlobalErrorBanner,
} from "../../components";
import { DecisionHero } from "./DecisionHero";
import { EvidenceAccordion } from "./EvidenceAccordion";
import { SecondaryActionBar } from "./SecondaryActionBar";
import "./styles.css";

export function AgentDChannelComparison({
  state,
  onRemoveChannel,
  onRetryChannel,
  onRetryGlobal,
}: ChannelComparisonRendererProps) {
  const heroRef = useRef<HTMLDivElement>(null);
  const loadedChannels = state.selectedChannelIds
    .map((id) => state.channelData[id])
    .filter(Boolean);

  const hasChannels = state.selectedChannelIds.length > 0;

  return (
    <section className="cc-agent cc-agent-d" aria-label="Action-Forward — Channel Comparison">
      {state.availableChannelsError ? (
        <GlobalErrorBanner error={state.availableChannelsError} onRetry={onRetryGlobal} />
      ) : null}

      {!hasChannels ? <EmptyComparisonState /> : null}

      {hasChannels ? (
        <div className="cc-d-content">
          <div ref={heroRef}>
            <DecisionHero
              winner={state.winner}
              budgetRecommendation={state.budgetRecommendation}
              channels={loadedChannels}
            />
          </div>

          <EvidenceAccordion
            state={state}
            loadedChannels={loadedChannels}
            dateRange={state.dateRange}
            onRemoveChannel={onRemoveChannel}
            onRetryChannel={onRetryChannel}
          />

          <SecondaryActionBar
            recommendation={state.budgetRecommendation}
            heroRef={heroRef}
          />
        </div>
      ) : null}
    </section>
  );
}
