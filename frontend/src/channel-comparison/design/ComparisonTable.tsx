import type { ComparisonChannelData, ChannelComparisonDerivedMetric } from "../../types/comparison";
import { formatCompact, formatROAS } from "../../lib/formatters";
import { displayChannelName } from "../core/constants";
import { ChannelIcon } from "./ChannelIcon";

interface ComparisonTableProps {
  channels: ComparisonChannelData[];
  derivedByChannelId: Record<string, ChannelComparisonDerivedMetric>;
  dateRangeLabel: string;
}

function confidenceLabel(level: string): string {
  if (level === "high") return "High Confidence";
  if (level === "medium") return "Medium Confidence";
  return "Low Confidence";
}

function formatDeltaForTable(label: string | null): string | null {
  if (!label) return null;
  const isNegative = label.includes(" lower") || label.includes(" less");
  const match = label.match(/\$[0-9.,]+/);
  if (!match) return null;
  const amount = match[0];
  const sign = isNegative ? "-" : "+";
  return `${sign}${amount}`;
}

export function ComparisonTable({ channels, derivedByChannelId, dateRangeLabel }: ComparisonTableProps) {
  return (
    <div className="dc-comparison-table-card">
      <h3 className="dc-table-title">Detailed comparison table ({dateRangeLabel})</h3>

      <table className="dc-comparison-table">
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
          {channels.map((ch) => {
            const level = ch.confidenceRange.level;
            const derived = derivedByChannelId[ch.channel.id];
            const name = displayChannelName(ch.channel.name, ch.channel.platform_type);

            const roasDelta = derived?.isBestByRoas ? null : formatDeltaForTable(derived?.roasDeltaLabel ?? null);
            const revDelta = derived?.isBestByRevenue ? null : formatDeltaForTable(derived?.revenueDeltaLabel ?? null);

            return (
              <tr key={ch.channel.id}>
                <td>
                  <div className="dc-table-channel-cell">
                    <ChannelIcon platformType={ch.channel.platform_type} size={20} />
                    <span className="dc-table-channel-name">{name}</span>
                  </div>
                </td>
                <td>{formatCompact(ch.performance.spend)}</td>
                <td>{formatCompact(ch.performance.revenue)}</td>
                <td className="dc-table-roas">{formatROAS(ch.performance.roas)}</td>
                <td>
                  <span className={`dc-confidence-badge ${level}`}>
                    {confidenceLabel(level)}
                  </span>
                </td>
                <td>
                  {roasDelta ? (
                    <span className="dc-table-negative">{roasDelta}</span>
                  ) : (
                    <span className="dc-table-dash">&mdash;</span>
                  )}
                </td>
                <td>
                  {revDelta ? (
                    <span className="dc-table-negative">{revDelta}</span>
                  ) : (
                    <span className="dc-table-dash">&mdash;</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
