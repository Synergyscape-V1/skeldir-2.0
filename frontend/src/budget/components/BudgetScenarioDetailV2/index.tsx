import React, { useCallback, useMemo, useState } from 'react';
import { ScenarioHeader } from './ScenarioHeader';
import { ScenarioParameterMatrix } from './ScenarioParameterMatrix';
import { ForecastingFanChart } from './ForecastingFanChart';
import { ScenarioComparisonRail } from './ScenarioComparisonRail';
import {
  SCENARIO,
  INITIAL_BUDGET_SCENARIO_TABS,
  MAX_SCENARIO_TABS,
  equalAllocationMatrixSnapshot,
  createBudgetScenarioTab,
  type MatrixParametersSnapshot,
  type BudgetScenarioTab,
} from './scenarioData';
import './budget-scenario-detail-v2.css';

export function BudgetScenarioDetailV2() {
  const [tabs, setTabs] = useState<BudgetScenarioTab[]>(() => INITIAL_BUDGET_SCENARIO_TABS.map((t) => ({
    ...t,
    draft: { ...t.draft, percents: { ...t.draft.percents } },
    saved: { ...t.saved, percents: { ...t.saved.percents } },
  })));
  const [activeTabId, setActiveTabId] = useState(() => INITIAL_BUDGET_SCENARIO_TABS[0]?.id ?? 'tab-q2-agg');

  const activeTab = useMemo(() => tabs.find((t) => t.id === activeTabId) ?? tabs[0], [tabs, activeTabId]);

  const setMatrixDraft = useCallback(
    (next: MatrixParametersSnapshot) => {
      setTabs((prev) =>
        prev.map((t) =>
          t.id === activeTabId
            ? { ...t, draft: { ...next, percents: { ...next.percents } } }
            : t
        )
      );
    },
    [activeTabId]
  );

  const handleMatrixSave = useCallback(() => {
    setTabs((prev) =>
      prev.map((t) => {
        if (t.id !== activeTabId) return t;
        const d = t.draft;
        return {
          ...t,
          name: d.scenarioName,
          saved: { ...d, percents: { ...d.percents } },
        };
      })
    );
  }, [activeTabId]);

  const handleMatrixParametersChange = useCallback((_snapshot: MatrixParametersSnapshot) => {
    void _snapshot;
    /* Debounced — wire ForecastingFanChart / API when projections are derived from matrix. */
  }, []);

  const handleSelectTab = useCallback((id: string) => {
    setActiveTabId(id);
  }, []);

  const handleNewScenario = useCallback(() => {
    setTabs((prev) => {
      if (prev.length >= MAX_SCENARIO_TABS) {
        window.alert(
          `You can have at most ${MAX_SCENARIO_TABS} saved scenarios in the rail. Remove or overwrite one to add another.`
        );
        return prev;
      }
      const names = new Set(prev.map((t) => t.name));
      let baseName = 'New scenario';
      let suffix = 2;
      while (names.has(baseName)) {
        baseName = `New scenario (${suffix})`;
        suffix += 1;
      }
      const snap = equalAllocationMatrixSnapshot(baseName);
      const id = `tab-new-${Date.now()}`;
      const tab = createBudgetScenarioTab(id, baseName, snap);
      queueMicrotask(() => setActiveTabId(id));
      return [...prev, tab];
    });
  }, []);

  return (
    <div className="bsdv2-page">
      <ScenarioHeader scenario={SCENARIO} />
      <div className="bsdv2-page-inner">
        <div className="bsdv2-split-grid">
          <div>
            <ScenarioParameterMatrix
              value={activeTab.draft}
              onChange={setMatrixDraft}
              savedSnapshot={activeTab.saved}
              onSave={handleMatrixSave}
              onParametersChange={handleMatrixParametersChange}
            />
          </div>
          <div className="bsdv2-chart-column">
            <ScenarioComparisonRail
              tabs={tabs.map((t) => ({ id: t.id, name: t.name }))}
              activeTabId={activeTab.id}
              onSelectTab={handleSelectTab}
              onNewScenario={handleNewScenario}
              maxTabs={MAX_SCENARIO_TABS}
            />
            <ForecastingFanChart matrixSnapshot={activeTab.draft} />
          </div>
        </div>
      </div>
    </div>
  );
}
