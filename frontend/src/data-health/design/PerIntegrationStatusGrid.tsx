import React, { useMemo } from "react";
import { RefreshCw, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import { PlatformIcon } from "./PlatformIcon";
import type {
  IntegrationStatusCard,
  IntegrityState,
  PerIntegrationSortBy,
  PerIntegrationStatusGridProps,
} from "./integrationStatusGridTypes";
import "./per-integration-status-grid.css";

const STATE_ORDER: Record<IntegrityState, number> = {
  critical: 0,
  needs_review: 1,
  healthy: 2,
};

const LABEL: Record<IntegrityState, string> = {
  healthy: "Healthy",
  needs_review: "Needs Review",
  critical: "Critical",
};

function sortIntegrations(
  list: IntegrationStatusCard[],
  sortBy: PerIntegrationSortBy,
): IntegrationStatusCard[] {
  const copy = [...list];
  if (sortBy === "severity") {
    copy.sort((a, b) => {
      const dr = STATE_ORDER[a.status.state] - STATE_ORDER[b.status.state];
      if (dr !== 0) return dr;
      return a.status.score - b.status.score;
    });
  } else if (sortBy === "name") {
    copy.sort((a, b) => a.displayName.localeCompare(b.displayName));
  } else {
    copy.sort((a, b) => {
      const ta = a.sync.lastSyncAt ? new Date(a.sync.lastSyncAt).getTime() : 0;
      const tb = b.sync.lastSyncAt ? new Date(b.sync.lastSyncAt).getTime() : 0;
      return tb - ta;
    });
  }
  return copy;
}

function StatusShield({ state }: { state: IntegrityState }) {
  const p = { size: 16, strokeWidth: 2.25, className: "pisg-card__shield", "aria-hidden": true as boolean };
  if (state === "healthy") return <ShieldCheck {...p} color="#059669" />;
  if (state === "needs_review") return <ShieldAlert {...p} color="#d97706" />;
  return <ShieldX {...p} color="#dc2626" />;
}

function revenueLine(card: IntegrationStatusCard): { text: string; variant: "ok" | "stale" | "bad" | "muted" } {
  if (card.sync.staleness === "stale" && card.status.state === "needs_review" && card.revenueMatch?.status === "partial") {
    return { text: "Stale data", variant: "stale" };
  }
  if (!card.revenueMatch) return { text: "—", variant: "muted" };
  const { percentage, status } = card.revenueMatch;
  if (status === "verified") return { text: `${percentage}% match · verified`, variant: "ok" };
  if (status === "partial") return { text: `${percentage}% match · partial`, variant: "stale" };
  return { text: `${percentage}% match · unverified`, variant: percentage === 0 ? "bad" : "stale" };
}

function cardClassName(card: IntegrationStatusCard): string {
  const base = "pisg-card";
  const state =
    card.status.state === "healthy"
      ? "pisg-card--healthy"
      : card.status.state === "needs_review"
        ? "pisg-card--needs_review"
        : "pisg-card--critical";
  const fg = card.fixGuidanceActive ? " pisg-card--fix-guidance" : "";
  return `${base} ${state}${fg}`;
}

function ariaSummary(card: IntegrationStatusCard): string {
  const st = card.status;
  const sync = card.sync.relativeTime;
  const rev = revenueLine(card).text;
  return `${card.displayName}: ${LABEL[st.state]}, score ${st.score}, threshold ${st.thresholdText}. Last sync ${sync}. Revenue ${rev}.`;
}

export function PerIntegrationStatusGrid({
  integrations,
  sortBy = "severity",
  onCardClick,
  onRefreshAll,
}: PerIntegrationStatusGridProps) {
  const sorted = useMemo(() => sortIntegrations(integrations, sortBy), [integrations, sortBy]);

  return (
    <section className="pisg" aria-labelledby="pisg-heading">
      <div className="pisg__header">
        <div className="pisg__title-block">
          <h2 id="pisg-heading">Per-Integration Status</h2>
          <p>Real-time health of connected platforms — integrity score, sync, and revenue verification at a glance.</p>
        </div>
        {onRefreshAll && (
          <button type="button" className="pisg__refresh" onClick={onRefreshAll}>
            <RefreshCw size={14} aria-hidden />
            Refresh all
          </button>
        )}
      </div>

      <div className="pisg__grid">
        {sorted.map((card) => {
          const rev = revenueLine(card);
          const lbl = LABEL[card.status.state];
          return (
            <article
              key={card.id}
              className={cardClassName(card)}
              tabIndex={0}
              aria-label={ariaSummary(card)}
              onClick={() => onCardClick(card.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onCardClick(card.id);
                }
              }}
            >
              <div className="pisg-card__platform">
                {card.icon ?? <PlatformIcon platform={card.platformIconKey} size={24} />}
                <span className="pisg-card__platform-name">{card.displayName}</span>
              </div>

              <div className="pisg-card__badge-row">
                <StatusShield state={card.status.state} />
                <div className="pisg-card__badge-text">
                  <div className="pisg-card__status-line">
                    <span className="pisg-card__dot" aria-hidden />
                    <span className="pisg-card__label">{lbl}</span>
                    <span className="pisg-card__score">({card.status.score})</span>
                  </div>
                  <span className="pisg-card__threshold">{card.status.thresholdText}</span>
                </div>
              </div>

              <div className="pisg-card__sync">Last: {card.sync.relativeTime}</div>

              <div
                className={`pisg-card__revenue${
                  rev.variant === "ok" ? " pisg-card__revenue--ok" : ""
                }${rev.variant === "stale" ? " pisg-card__revenue--stale-note" : ""}${
                  rev.variant === "bad" ? " pisg-card__revenue--bad" : ""
                }${rev.variant === "muted" ? " pisg-card__revenue--muted" : ""}`}
              >
                {rev.text}
              </div>

              <div className="pisg-card__actions">
                {card.actions.primary && (
                  <button
                    type="button"
                    className={`pisg-card__btn ${card.actions.primary.destructive ? "pisg-card__btn--danger" : "pisg-card__btn--primary"}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      card.actions.primary?.action();
                    }}
                  >
                    {card.actions.primary.label}
                  </button>
                )}
                {card.actions.secondary && (
                  <button
                    type="button"
                    className="pisg-card__btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      card.actions.secondary?.action();
                    }}
                  >
                    {card.actions.secondary.label}
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
