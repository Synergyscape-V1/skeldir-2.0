import { useMemo } from "react";
import type { ChannelComparisonRendererProps } from "../../types/comparison";
import { DATE_RANGE_LABELS } from "../core/constants";
import { BudgetBanner } from "./BudgetBanner";
import { ChannelCard } from "./ChannelCard";
import { ConfidenceChart } from "./ConfidenceChart";
import { ComparisonTable } from "./ComparisonTable";
import { ModelRecommendation } from "./ModelRecommendation";
import "./design-comparison.css";

export function DesignChannelComparison({
  state,
  onRetryGlobal,
}: ChannelComparisonRendererProps) {
  const { selectedChannelIds, channelData, loading, errors, winner, budgetRecommendation, derivedByChannelId, dateRange } = state;

  const isAnyLoading = Object.values(loading).some(Boolean);

  const loadedChannels = useMemo(
    () => selectedChannelIds.map((id) => channelData[id]).filter(Boolean),
    [selectedChannelIds, channelData]
  );

  const globalError = useMemo(
    () => Object.values(errors).find((e) => e !== null),
    [errors]
  );

  const dateRangeLabel = DATE_RANGE_LABELS[dateRange] ?? "Last 30 Days";
  const gridCols = Math.min(loadedChannels.length, 3);

  // Empty state
  if (selectedChannelIds.length === 0) {
    return (
      <div className="dc-root">
        <div className="dc-empty-state">
          <p>No channels selected.</p>
          <p>Use the selector above to add channels for comparison.</p>
        </div>
      </div>
    );
  }

  // Loading state
  if (isAnyLoading && loadedChannels.length === 0) {
    return (
      <div className="dc-root">
        <div className="dc-loading-skeleton" />
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${gridCols || 3}, 1fr)`, gap: 16 }}>
          {selectedChannelIds.map((id) => (
            <div key={id} className="dc-loading-skeleton" style={{ height: 240 }} />
          ))}
        </div>
        <div className="dc-loading-skeleton" style={{ height: 200 }} />
      </div>
    );
  }

  // Global error
  if (globalError && loadedChannels.length === 0) {
    return (
      <div className="dc-root">
        <div className="dc-error-banner">
          <p>{globalError.message}</p>
          <button type="button" onClick={onRetryGlobal}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="dc-root">
      {/* Budget recommendation banner */}
      {budgetRecommendation && (
        <BudgetBanner recommendation={budgetRecommendation} />
      )}

      {/* Channel cards */}
      <div
        className="dc-cards-grid"
        style={{ gridTemplateColumns: `repeat(${gridCols}, 1fr)` }}
      >
        {loadedChannels.map((ch) => {
          const derived = derivedByChannelId[ch.channel.id];
          if (!derived) return null;
          return (
            <ChannelCard
              key={ch.channel.id}
              data={ch}
              derived={derived}
              winner={winner}
            />
          );
        })}
      </div>

      {/* Confidence chart */}
      <ConfidenceChart channels={loadedChannels} />

      {/* Bottom section: table + recommendation */}
      <div className="dc-bottom-grid">
        <ComparisonTable
          channels={loadedChannels}
          derivedByChannelId={derivedByChannelId}
          dateRangeLabel={dateRangeLabel}
        />
        <ModelRecommendation
          winner={winner}
          recommendation={budgetRecommendation}
        />
      </div>
    </div>
  );
}
