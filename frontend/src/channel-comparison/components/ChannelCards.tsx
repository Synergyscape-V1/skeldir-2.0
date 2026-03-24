import React from "react";
import { formatCompact } from "../../lib/formatters";
import type { ChannelComparisonViewState } from "../../types/comparison";
import { confidenceTierDescription } from "../core/logic";
import { displayChannelName, platformMeta } from "../core/constants";

interface ChannelCardsProps {
  state: ChannelComparisonViewState;
  className?: string;
  onRemoveChannel: (channelId: string) => void;
  onRetryChannel: (channelId: string) => void;
}

export function ChannelCards({
  state,
  className,
  onRemoveChannel,
  onRetryChannel,
}: ChannelCardsProps) {
  return (
    <section className={`cc-panels-grid ${className ?? ""}`}>
      {state.selectedChannelIds.map((channelId, index) => {
        const data = state.channelData[channelId];
        const error = state.errors[channelId];
        const isLoading = state.loading[channelId];
        const derived = state.derivedByChannelId[channelId];
        const colorClass = `cc-panel-color-${index + 1}`;
        const name = data ? displayChannelName(data.channel.name, data.channel.platform_type) : channelId;
        const meta = data ? platformMeta(data.channel.platform_type) : null;
        const isWinner = derived?.isBestByRoas && state.selectedChannelIds.length >= 2;
        const tier = data?.confidenceRange.level;

        return (
          <article
            key={channelId}
            className={`cc-panel ${colorClass}`}
            role="article"
            aria-label={`${name} performance data`}
          >
            <header>
              <span className="cc-panel-name">
                {meta ? <img src={meta.iconSrc} alt={meta.label} width={24} height={24} /> : null}
                {name}
              </span>
              <div className="cc-panel-header-right">
                {!isLoading && !error && data && tier ? (
                  <span className={`cc-panel-badge confidence-${tier}`}>
                    {confidenceTierDescription(tier)}
                  </span>
                ) : null}
                <button type="button" onClick={() => onRemoveChannel(channelId)} aria-label={`Remove ${name}`}>
                  ×
                </button>
              </div>
            </header>

            {isLoading ? (
              <div className="cc-panel-loading" aria-busy="true">
                <div className="cc-skeleton-line wide" />
                <div className="cc-skeleton-line short" />
                <div className="cc-skeleton-line short" />
              </div>
            ) : null}

            {!isLoading && error ? (
              <div className="cc-panel-error">
                <p>Failed to load channel data</p>
                <small>{error.message}</small>
                <small>Error ID: {error.correlationId ?? "unavailable"}</small>
                <button type="button" onClick={() => onRetryChannel(channelId)}>
                  Retry
                </button>
              </div>
            ) : null}

            {!isLoading && !error && data ? (
              <div className="cc-panel-body">
                <div className="cc-panel-hero">
                  <span className="cc-panel-roas-value">{data.performance.roas.toFixed(2)}</span>
                  <span className="cc-panel-roas-label">ROAS</span>
                </div>

                {isWinner ? (
                  <p className="cc-panel-winner-tag">✓ Top performer</p>
                ) : derived?.roasDeltaLabel ? (
                  <p className="cc-panel-delta">↓ {derived.roasDeltaLabel.replace(/^[+-]?\$/, "").replace(" higher", " higher than ").replace(" lower", " lower than ").replace(" vs ", "")}</p>
                ) : null}

                <div className="cc-panel-footer">
                  <span>Spend {formatCompact(data.performance.spend)}</span>
                  <span>Revenue {formatCompact(data.performance.revenue)}</span>
                </div>
              </div>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}
