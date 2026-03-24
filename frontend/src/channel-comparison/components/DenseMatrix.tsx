import React from "react";
import { formatCompact } from "../../lib/formatters";
import type { ChannelComparisonViewState } from "../../types/comparison";
import { confidenceTierDescription } from "../core/logic";
import { displayChannelName, platformMeta, DATE_RANGE_LABELS } from "../core/constants";

interface DenseMatrixProps {
  state: ChannelComparisonViewState;
}

export function DenseMatrix({ state }: DenseMatrixProps) {
  return (
    <section className="cc-dense-matrix">
      <h2>Detailed comparison table ({DATE_RANGE_LABELS[state.dateRange]})</h2>
      <div className="cc-dense-scroll">
        <table>
          <thead>
            <tr>
              <th>Channel</th>
              <th>Spend</th>
              <th>Revenue</th>
              <th>ROAS</th>
              <th>Confidence</th>
              <th>Delta vs Best ROAS</th>
              <th>Delta vs Best Rev</th>
            </tr>
          </thead>
          <tbody>
            {state.selectedChannelIds.map((channelId) => {
              const data = state.channelData[channelId];
              const isLoading = state.loading[channelId];
              const error = state.errors[channelId];
              const derived = state.derivedByChannelId[channelId];

              if (isLoading) {
                return (
                  <tr key={channelId}>
                    <td colSpan={7}>
                      <div className="cc-skeleton-line wide" />
                    </td>
                  </tr>
                );
              }

              if (error) {
                return (
                  <tr key={channelId} className="cc-dense-error-row">
                    <td colSpan={7}>Error loading channel data</td>
                  </tr>
                );
              }

              if (!data) return null;

              const name = displayChannelName(data.channel.name, data.channel.platform_type);
              const meta = platformMeta(data.channel.platform_type);
              const tier = data.confidenceRange.level;
              const isBestRoas = derived?.isBestByRoas;
              const isBestRevenue = derived?.isBestByRevenue;

              return (
                <tr key={channelId}>
                  <td className="cc-dense-channel-cell">
                    <img src={meta.iconSrc} alt={meta.label} width={20} height={20} />
                    <span>{name}</span>
                  </td>
                  <td>{formatCompact(data.performance.spend)}</td>
                  <td>{formatCompact(data.performance.revenue)}</td>
                  <td><strong>{data.performance.roas.toFixed(2)}</strong></td>
                  <td>
                    <span className={`cc-dense-badge confidence-${tier}`}>
                      {confidenceTierDescription(tier)}
                    </span>
                  </td>
                  <td>{isBestRoas ? "—" : derived?.roasDeltaLabel?.split(" vs ")[0] ?? "—"}</td>
                  <td>{isBestRevenue ? "—" : derived?.revenueDeltaLabel?.split(" vs ")[0] ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
