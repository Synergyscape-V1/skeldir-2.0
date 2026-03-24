import React, { useMemo, useRef, useState } from "react";
import { AgentShellDataHealth } from "./AgentShellDataHealth";
import { AGENTS } from "./agents";
import type { DataHealthScenario, DataHealthUiState } from "../data-health/core/types";

const viewports: Record<"375" | "768" | "1440", number> = {
  "375": 375,
  "768": 768,
  "1440": 1440,
};

export function CompareDataHealthOverview() {
  const [scenario, setScenario] = useState<DataHealthScenario>("warning");
  const [uiState, setUiState] = useState<DataHealthUiState>("steady");
  const [viewport, setViewport] = useState<"375" | "768" | "1440">("1440");
  const [density, setDensity] = useState<90 | 100>(100);
  const [stale, setStale] = useState(false);
  const syncingRef = useRef(false);
  const panelRefs = useRef<Array<HTMLDivElement | null>>([]);

  const viewportWidth = useMemo(() => viewports[viewport], [viewport]);

  const syncScroll = (source: HTMLDivElement) => {
    if (syncingRef.current) return;
    syncingRef.current = true;
    const top = source.scrollTop;
    panelRefs.current.forEach((panel) => {
      if (panel && panel !== source) {
        panel.scrollTop = top;
      }
    });
    requestAnimationFrame(() => {
      syncingRef.current = false;
    });
  };

  return (
    <div style={{ padding: 16 }}>
      <h1 style={{ fontFamily: "Segoe UI, sans-serif" }}>Compare All - Data Health</h1>
      <p style={{ fontFamily: "Segoe UI, sans-serif" }}>All five iterations render with synchronized scenario, state, and viewport controls.</p>
      <div className="compare-controls">
        <label>
          Scenario
          <select value={scenario} onChange={(e) => setScenario(e.target.value as DataHealthScenario)}>
            <option value="good">Good Health</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </label>
        <label>
          UI State
          <select value={uiState} onChange={(e) => setUiState(e.target.value as DataHealthUiState)}>
            <option value="steady">Steady</option>
            <option value="initial_loading">Initial Loading</option>
            <option value="error">Error</option>
            <option value="no_data">No Data</option>
          </select>
        </label>
        <label>
          Viewport
          <select value={viewport} onChange={(e) => setViewport(e.target.value as "375" | "768" | "1440") }>
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
          Stale Data
          <input type="checkbox" checked={stale} onChange={(e) => setStale(e.target.checked)} />
        </label>
      </div>
      <div className="compare-all-stack">
        {AGENTS.map((agent, index) => (
          <article className="compare-all-item" key={agent.id}>
            <header>
              Iteration {index + 1}: {agent.title}
            </header>
            <div
              className="compare-all-frame"
              style={{ width: viewportWidth, maxHeight: 860, overflowY: "auto" }}
              ref={(node) => {
                panelRefs.current[index] = node;
              }}
              onScroll={(event) => syncScroll(event.currentTarget)}
            >
              <AgentShellDataHealth
                theme={agent}
                scenario={scenario}
                uiState={uiState}
                stale={stale}
                density={density}
              />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
