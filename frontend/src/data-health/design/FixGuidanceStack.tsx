import React, { useId, useMemo, useState } from "react";
import { FixGuidanceCard } from "./FixGuidanceCard";
import type { FixGuidanceCardProps, FixGuidanceStackProps, FixGuidanceSeverity } from "./fixGuidanceTypes";
import "./fix-guidance.css";

const SEVERITY_ORDER: Record<FixGuidanceSeverity, number> = {
  critical: 0,
  caution: 1,
  info: 2,
};

function sortCards(
  cards: FixGuidanceCardProps[],
  order: NonNullable<FixGuidanceStackProps["sortOrder"]>,
): FixGuidanceCardProps[] {
  const copy = [...cards];
  if (order === "severity_desc") {
    copy.sort((a, b) => {
      const dr = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
      if (dr !== 0) return dr;
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    });
  } else {
    copy.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }
  return copy;
}

function applyFilter(
  cards: FixGuidanceCardProps[],
  filter: FixGuidanceStackProps["filter"],
): FixGuidanceCardProps[] {
  if (!filter || filter === "all") return cards;
  if (filter === "critical") return cards.filter((c) => c.severity === "critical");
  if (filter === "actionable") return cards.filter((c) => c.severity === "critical" || c.severity === "caution");
  return cards;
}

export function FixGuidanceStack({
  cards,
  maxVisible = 3,
  sortOrder = "severity_desc",
  filter = "all",
  onViewAll,
}: FixGuidanceStackProps) {
  const stackTitleId = useId();
  const [showAll, setShowAll] = useState(false);

  const processed = useMemo(() => {
    const f = applyFilter(cards, filter);
    return sortCards(f, sortOrder);
  }, [cards, filter, sortOrder]);

  const visible = showAll ? processed : processed.slice(0, maxVisible);
  const hiddenCount = Math.max(0, processed.length - maxVisible);

  const criticalCount = processed.filter((c) => c.severity === "critical").length;

  return (
    <div className="fgc-root">
      <section className="fgc-panel" aria-labelledby={stackTitleId}>
        <header className="fgc-panel-header">
          <div>
            <h2
              id={stackTitleId}
              style={{
                margin: 0,
                fontFamily: "'DM Sans', system-ui, sans-serif",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "#374151",
              }}
            >
              Fix Guidance Required
            </h2>
            <p
              style={{
                margin: "4px 0 0",
                fontFamily: "'DM Sans', system-ui, sans-serif",
                fontSize: 11,
                fontWeight: 400,
                color: "#64748b",
                maxWidth: "100%",
                lineHeight: 1.35,
              }}
            >
              Resolve data health issues to maintain attribution accuracy — operational runbook, not just status.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {criticalCount > 1 && (
              <button
                type="button"
                className="fgc-btn-secondary"
                onClick={() => {
                  const first = processed.find((c) => c.severity === "critical");
                  first?.remediation.primary.action();
                }}
              >
                Resolve all critical
              </button>
            )}
            {onViewAll && (
              <button type="button" className="fgc-view-all" onClick={onViewAll}>
                View all →
              </button>
            )}
          </div>
        </header>

        <div className="fgc-panel-body">
          {visible.map((card) => (
            <FixGuidanceCard key={card.id} {...card} />
          ))}
        </div>

        {!showAll && hiddenCount > 0 && (
          <div className="fgc-panel-footer">
            <button type="button" className="fgc-show-more" onClick={() => setShowAll(true)}>
              Show {hiddenCount} more
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
