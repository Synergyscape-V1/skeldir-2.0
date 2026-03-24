import React, { useMemo, useState } from "react";
import type { DateRangeValue } from "../types/channel";
import type { ChannelComparisonUiState, ComparisonScenario } from "../types/comparison";
import { AgentShellChannelComparison } from "./AgentShellChannelComparison";
import { AGENTS } from "./agents";
import { ChannelComparisonEvaluationPanel } from "../channel-comparison/evaluation/ChannelComparisonEvaluationPanel";
import { CHANNEL_COMPARISON_MANIFESTS } from "../channel-comparison/core/manifests";

const viewports: Record<"375" | "768" | "1440", number> = {
  "375": 375,
  "768": 768,
  "1440": 1440,
};

export function CompareChannelComparisonOverview() {
  const [scenario, setScenario] = useState<ComparisonScenario>("default");
  const [uiState, setUiState] = useState<ChannelComparisonUiState>("populated");
  const [viewport, setViewport] = useState<"375" | "768" | "1440">("1440");
  const [density, setDensity] = useState<90 | 100>(100);
  const [dateRange, setDateRange] = useState<DateRangeValue>("last_30_days");
  const viewportWidth = useMemo(() => viewports[viewport], [viewport]);

  return (
    <div style={{ padding: 16 }}>
      <h1 style={{ fontFamily: "Segoe UI, sans-serif" }}>Compare All - Channel Comparison</h1>
      <p style={{ fontFamily: "Segoe UI, sans-serif" }}>
        Side-by-side synchronized evaluation across five independent channel comparison hypotheses.
      </p>
      <div className="compare-controls">
        <label>
          Scenario
          <select value={scenario} onChange={(event) => setScenario(event.target.value as ComparisonScenario)}>
            <option value="default">Default (3 channels)</option>
            <option value="no_winner">No Winner</option>
            <option value="three_channels">Three Channels</option>
            <option value="four_channels">Four Channels</option>
            <option value="empty">Empty</option>
          </select>
        </label>
        <label>
          UI State
          <select value={uiState} onChange={(event) => setUiState(event.target.value as ChannelComparisonUiState)}>
            <option value="populated">Populated</option>
            <option value="loading">Loading</option>
            <option value="error_panel">Error (Panel)</option>
            <option value="error_global">Error (Global)</option>
            <option value="empty">Empty</option>
          </select>
        </label>
        <label>
          Viewport
          <select value={viewport} onChange={(event) => setViewport(event.target.value as "375" | "768" | "1440") }>
            <option value="375">Mobile 375</option>
            <option value="768">Tablet 768</option>
            <option value="1440">Desktop 1440</option>
          </select>
        </label>
        <label>
          Date Range
          <select value={dateRange} onChange={(event) => setDateRange(event.target.value as DateRangeValue)}>
            <option value="last_7_days">Last 7 Days</option>
            <option value="last_30_days">Last 30 Days</option>
            <option value="last_60_days">Last 60 Days</option>
            <option value="last_90_days">Last 90 Days</option>
          </select>
        </label>
        <label>
          Density
          <select value={density} onChange={(event) => setDensity(Number(event.target.value) as 90 | 100)}>
            <option value={100}>100%</option>
            <option value={90}>90%</option>
          </select>
        </label>
      </div>

      <section className="cc-compare-row" aria-label="All five channel comparison variants">
        {AGENTS.map((agent) => (
          <article className="cc-compare-column" key={agent.id}>
            <header>
              <h2>{agent.navLabel}</h2>
              <p>{agent.signature}</p>
            </header>
            <div className="cc-compare-frame" style={{ width: viewportWidth }}>
              <AgentShellChannelComparison
                theme={agent}
                scenario={scenario}
                uiState={uiState}
                density={density}
                dateRange={dateRange}
              />
            </div>
          </article>
        ))}
      </section>

      <ChannelComparisonEvaluationPanel manifests={CHANNEL_COMPARISON_MANIFESTS} />
    </div>
  );
}
