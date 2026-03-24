import React from "react";
import { formatCurrency } from "../../../lib/formatters";
import type { ChannelComparisonDerivedMetric, ComparisonChannelData } from "../../../types/comparison";
import { displayChannelName, platformMeta } from "../../core/constants";

interface ConfidenceTierCardsProps {
  channels: ComparisonChannelData[];
  derivedByChannelId: Record<string, ChannelComparisonDerivedMetric>;
}

const TIERS: Array<{ key: "high" | "medium" | "low"; label: string }> = [
  { key: "high", label: "High Confidence Channels" },
  { key: "medium", label: "Medium Confidence Channels" },
  { key: "low", label: "Low Confidence Channels" },
];

export function ConfidenceTierCards({ channels, derivedByChannelId }: ConfidenceTierCardsProps) {
  return (
    <div className="cc-c-tier-groups">
      {TIERS.map((tier) => {
        const tierChannels = channels.filter((c) => c.confidenceRange.level === tier.key);
        if (tierChannels.length === 0) return null;

        return (
          <section key={tier.key} className={`cc-c-tier-group cc-c-tier-${tier.key}`}>
            <h4 className="cc-c-tier-header">{tier.label}</h4>
            <div className="cc-c-tier-cards">
              {tierChannels.map((channel) => {
                const meta = platformMeta(channel.channel.platform_type);
                const name = displayChannelName(channel.channel.name, channel.channel.platform_type);
                const derived = derivedByChannelId[channel.channel.id];

                return (
                  <article
                    key={channel.channel.id}
                    className="cc-c-tier-card"
                    role="article"
                    aria-label={`${name} performance data`}
                  >
                    <header className="cc-c-card-header">
                      <img src={meta.iconSrc} alt={meta.label} width={24} height={24} />
                      <span>{name}</span>
                    </header>
                    <div className="cc-c-card-metrics">
                      <div className="cc-c-metric">
                        <label>ROAS</label>
                        <strong>{channel.performance.roas.toFixed(2)}</strong>
                        {derived?.roasDeltaLabel ? <small>{derived.roasDeltaLabel}</small> : null}
                      </div>
                      <div className="cc-c-metric">
                        <label>Revenue</label>
                        <strong>{formatCurrency(channel.performance.revenue)}</strong>
                        {derived?.revenueDeltaLabel ? <small>{derived.revenueDeltaLabel}</small> : null}
                      </div>
                      <div className="cc-c-metric">
                        <label>Spend</label>
                        <strong>{formatCurrency(channel.performance.spend)}</strong>
                      </div>
                      <div className="cc-c-metric">
                        <label>Conv.</label>
                        <strong>{channel.performance.conversions}</strong>
                        {derived?.conversionDeltaLabel ? <small>{derived.conversionDeltaLabel}</small> : null}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
