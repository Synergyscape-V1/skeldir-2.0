import React from "react";
import { formatCurrency } from "../../../lib/formatters";
import type { ChannelComparisonViewState } from "../../../types/comparison";
import { confidenceTierDescription } from "../../core/logic";
import { displayChannelName, platformMeta } from "../../core/constants";

interface DenseComparisonTableProps {
  state: ChannelComparisonViewState;
  onRemoveChannel: (channelId: string) => void;
  onRetryChannel: (channelId: string) => void;
}

type MetricKey = "roas" | "revenue" | "spend" | "conversions" | "confidence_range" | "confidence_level";

const METRICS: { key: MetricKey; label: string }[] = [
  { key: "roas", label: "ROAS" },
  { key: "revenue", label: "REVENUE" },
  { key: "spend", label: "SPEND" },
  { key: "conversions", label: "CONVERSIONS" },
  { key: "confidence_range", label: "CONF. RANGE" },
  { key: "confidence_level", label: "CONF. LEVEL" },
];

function cellValue(metric: MetricKey, state: ChannelComparisonViewState, channelId: string): string {
  const data = state.channelData[channelId];
  if (state.loading[channelId]) return "\u2014";
  if (state.errors[channelId]) return "Error";
  if (!data) return "\u2014";

  switch (metric) {
    case "roas": return data.performance.roas.toFixed(2);
    case "revenue": return formatCurrency(data.performance.revenue);
    case "spend": return formatCurrency(data.performance.spend);
    case "conversions": return String(data.performance.conversions);
    case "confidence_range": return `${data.confidenceRange.low.toFixed(2)}\u2013${data.confidenceRange.high.toFixed(2)}`;
    case "confidence_level": return confidenceTierDescription(data.confidenceRange.level);
  }
}

function cellDelta(metric: MetricKey, state: ChannelComparisonViewState, channelId: string): string | null {
  const derived = state.derivedByChannelId[channelId];
  if (!derived) return null;
  switch (metric) {
    case "roas": return derived.roasDeltaLabel;
    case "revenue": return derived.revenueDeltaLabel;
    case "conversions": return derived.conversionDeltaLabel;
    default: return null;
  }
}

export function DenseComparisonTable({ state, onRemoveChannel, onRetryChannel }: DenseComparisonTableProps) {
  const ids = state.selectedChannelIds;

  return (
    <section className="cc-b-table-wrap">
      <div className="cc-b-table-scroll">
        <table className="cc-b-table" role="table">
          <thead>
            <tr>
              <th className="cc-b-metric-col">Metric</th>
              {ids.map((channelId) => {
                const data = state.channelData[channelId];
                const name = data ? displayChannelName(data.channel.name, data.channel.platform_type) : channelId;
                const meta = data ? platformMeta(data.channel.platform_type) : null;
                return (
                  <th key={channelId} className="cc-b-channel-col">
                    <span className="cc-b-th-inner">
                      {meta ? <img src={meta.iconSrc} alt={meta.label} width={20} height={20} /> : null}
                      <span>{name}</span>
                      <button type="button" onClick={() => onRemoveChannel(channelId)} aria-label={`Remove ${name}`}>&times;</button>
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {ids.some((id) => state.loading[id]) ? (
              <tr className="cc-b-loading-row">
                <td colSpan={ids.length + 1} aria-busy="true">
                  <div className="cc-skeleton-line wide" />
                  <div className="cc-skeleton-line short" />
                  <div className="cc-skeleton-line wide" />
                </td>
              </tr>
            ) : null}

            {ids.map((id) => {
              const error = state.errors[id];
              if (!error || state.loading[id]) return null;
              const data = state.channelData[id];
              const name = data ? data.channel.name : id;
              return (
                <tr key={`err-${id}`} className="cc-b-error-row">
                  <td colSpan={ids.length + 1}>
                    <span>{name}: Failed to load</span>
                    <button type="button" onClick={() => onRetryChannel(id)}>Retry</button>
                  </td>
                </tr>
              );
            })}

            {!ids.every((id) => state.loading[id]) ? METRICS.map((metric) => (
              <tr key={metric.key}>
                <td className="cc-b-metric-label">{metric.label}</td>
                {ids.map((channelId) => {
                  const value = cellValue(metric.key, state, channelId);
                  const delta = cellDelta(metric.key, state, channelId);
                  const data = state.channelData[channelId];
                  const tier = metric.key === "confidence_level" && data
                    ? data.confidenceRange.level
                    : null;
                  return (
                    <td key={`${metric.key}-${channelId}`} className={tier ? `cc-b-tier-${tier}` : undefined}>
                      <strong>{value}</strong>
                      {delta ? <small>{delta}</small> : null}
                    </td>
                  );
                })}
              </tr>
            )) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
