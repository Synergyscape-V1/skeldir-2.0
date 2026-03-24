import React, { useMemo, useState } from "react";
import { AGENTS } from "./agents";
import { AgentShellCommandCenter } from "./AgentShellCommandCenter";
import type { DashboardScenario, DatasetVariant } from "../types/dashboard";

const viewports: Record<"375" | "768" | "1440", number> = {
  "375": 375,
  "768": 768,
  "1440": 1440,
};

export function CompareOverview() {
  const [scenario, setScenario] = useState<DashboardScenario>("ready");
  const [viewport, setViewport] = useState<"375" | "768" | "1440">("1440");
  const [density, setDensity] = useState<90 | 100>(100);
  const [dataset, setDataset] = useState<DatasetVariant>("mixed");

  const viewportWidth = useMemo(() => viewports[viewport], [viewport]);

  return (
    <div style={{ padding: 16 }}>
      <h1 style={{ fontFamily: "Segoe UI, sans-serif" }}>Compare Overview</h1>
      <p style={{ fontFamily: "Segoe UI, sans-serif" }}>
        All five variants share the same scenario + dataset to preserve fair comparison.
      </p>
      <div className="compare-controls">
        <label>
          Scenario
          <select value={scenario} onChange={(e) => setScenario(e.target.value as DashboardScenario)}>
            <option value="ready">Ready</option>
            <option value="loading">Loading</option>
            <option value="empty">Empty</option>
            <option value="error">Error</option>
            <option value="polling_degraded">Polling-Degraded</option>
          </select>
        </label>
        <label>
          Viewport
          <select value={viewport} onChange={(e) => setViewport(e.target.value as "375" | "768" | "1440")}>
            <option value="375">Mobile 375</option>
            <option value="768">Tablet 768</option>
            <option value="1440">Desktop 1440</option>
          </select>
        </label>
        <label>
          Density
          <select value={density} onChange={(e) => setDensity(Number(e.target.value) as 90 | 100)}>
            <option value={100}>100%</option>
            <option value={90}>90%</option>
          </select>
        </label>
        <label>
          Dataset
          <select value={dataset} onChange={(e) => setDataset(e.target.value as DatasetVariant)}>
            <option value="high">high</option>
            <option value="mixed">mixed</option>
            <option value="low">low</option>
          </select>
        </label>
      </div>

      <div className="overview-grid">
        {AGENTS.map((agent) => (
          <article key={agent.id} className="overview-panel">
            <h2>{agent.navLabel}</h2>
            <div className="overview-viewport" style={{ width: viewportWidth }}>
              <AgentShellCommandCenter theme={agent} scenario={scenario} dataset={dataset} density={density} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

