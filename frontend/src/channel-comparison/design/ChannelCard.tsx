import type { ComparisonChannelData, ChannelComparisonDerivedMetric, WinnerDeclaration } from "../../types/comparison";
import { formatCompact } from "../../lib/formatters";
import { ChannelIcon } from "./ChannelIcon";
import { displayChannelName } from "../core/constants";

interface ChannelCardProps {
  data: ComparisonChannelData;
  derived: ChannelComparisonDerivedMetric;
  winner: WinnerDeclaration | null;
}

function confidenceLabel(level: string): string {
  if (level === "high") return "High Confidence";
  if (level === "medium") return "Medium Confidence";
  return "Low Confidence";
}

export function ChannelCard({ data, derived, winner }: ChannelCardProps) {
  const roas = data.performance.roas;
  const level = data.confidenceRange.level;
  const isTop = derived.isBestByRoas;
  const channelName = displayChannelName(data.channel.name, data.channel.platform_type);

  const deltaFromBest = winner && !isTop
    ? Math.abs(roas - winner.roas)
    : null;

  const bestName = winner ? displayChannelName(winner.channelName, data.channel.platform_type) : null;

  return (
    <div className={`metric-card dc-channel-card${isTop ? " is-top-performer" : ""}`}>
      <div className="dc-card-header">
        <div className="dc-card-channel-info">
          <ChannelIcon platformType={data.channel.platform_type} size={22} />
          <span className="dc-card-channel-name">{channelName}</span>
        </div>
        <span className={`dc-confidence-badge ${level}`}>
          {confidenceLabel(level)}
        </span>
      </div>

      {/* Hero metric */}
      <div className="dc-card-hero">
        <span className="dc-card-hero-roas">{roas.toFixed(2)}</span>
        <span className="dc-card-hero-label">ROAS</span>
      </div>

      {/* Performance context */}
      <div className="dc-card-context">
        {isTop ? (
          <div className="dc-card-top-performer">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Top performer
          </div>
        ) : deltaFromBest !== null ? (
          <div className="dc-card-delta">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <line x1="12" y1="5" x2="12" y2="19" />
              <polyline points="19 12 12 19 5 12" />
            </svg>
            <span className="dc-card-delta-value">{deltaFromBest.toFixed(2)}</span>
            <span className="dc-card-delta-label">lower than {bestName ?? "best"}</span>
          </div>
        ) : null}
      </div>

      {/* Footer metrics */}
      <div className="dc-card-footer">
        <span className="dc-card-footer-metric">
          Spend <span className="dc-card-footer-value">{formatCompact(data.performance.spend)}</span>
        </span>
        <span className="dc-card-footer-metric">
          Revenue <span className="dc-card-footer-value">{formatCompact(data.performance.revenue)}</span>
        </span>
      </div>
    </div>
  );
}
