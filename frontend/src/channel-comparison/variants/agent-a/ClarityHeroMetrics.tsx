import React from "react";
import { formatCurrency } from "../../../lib/formatters";
import type { ChannelComparisonViewState } from "../../../types/comparison";
import { displayChannelName, platformMeta } from "../../core/constants";

interface ClarityHeroMetricsProps {
  state: ChannelComparisonViewState;
  onRemoveChannel: (channelId: string) => void;
  onRetryChannel: (channelId: string) => void;
}

export function ClarityHeroMetrics({
  state,
  onRemoveChannel,
  onRetryChannel,
}: ClarityHeroMetricsProps) {
  return (
    <section className="cc-a-hero-row" aria-label="Channel ROAS overview">
      {state.selectedChannelIds.map((channelId) => {
        const data = state.channelData[channelId];
        const isLoading = state.loading[channelId];
        const error = state.errors[channelId];
        const derived = state.derivedByChannelId[channelId];
        const meta = data ? platformMeta(data.channel.platform_type) : null;
        const name = data
          ? displayChannelName(data.channel.name, data.channel.platform_type)
          : channelId;
        const tier = data?.confidenceRange.level ?? "medium";

        return (
          <article
            key={channelId}
            className={`cc-a-hero-cell cc-a-tier-${tier}`}
            role="article"
            aria-label={`${name} performance data`}
          >
            <div className="cc-a-hero-header">
              <span className="cc-a-hero-name">
                {meta ? (
                  <img src={meta.iconSrc} alt={meta.label} width={24} height={24} />
                ) : null}
                {name}
              </span>
              <button type="button" onClick={() => onRemoveChannel(channelId)} aria-label={`Remove ${name}`}>
                &times;
              </button>
            </div>

            {isLoading ? (
              <div className="cc-a-hero-loading" aria-busy="true">
                <div className="cc-skeleton-line wide" />
                <div className="cc-skeleton-line short" />
              </div>
            ) : null}

            {!isLoading && error ? (
              <div className="cc-a-hero-error">
                <p>Failed to load</p>
                <button type="button" onClick={() => onRetryChannel(channelId)}>
                  Retry
                </button>
              </div>
            ) : null}

            {!isLoading && !error && data ? (
              <div className="cc-a-hero-body">
                <span className="cc-a-hero-roas">{data.performance.roas.toFixed(2)}</span>
                <span className="cc-a-hero-roas-label">ROAS</span>
                {derived?.roasDeltaLabel ? (
                  <span className="cc-a-hero-delta">{derived.roasDeltaLabel}</span>
                ) : null}
                <div className="cc-a-hero-secondary">
                  <span>
                    <em>Revenue</em> {formatCurrency(data.performance.revenue)}
                  </span>
                  <span>
                    <em>Spend</em> {formatCurrency(data.performance.spend)}
                  </span>
                  <span>
                    <em>Conv.</em> {data.performance.conversions}
                  </span>
                </div>
              </div>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}
