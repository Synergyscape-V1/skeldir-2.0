import React from 'react';
import { Plus } from 'lucide-react';

export function ScenarioComparisonRail({
  tabs,
  activeTabId,
  onSelectTab,
  onNewScenario,
  maxTabs = 5,
}: {
  tabs: { id: string; name: string }[];
  activeTabId: string;
  onSelectTab: (id: string) => void;
  onNewScenario: () => void;
  maxTabs?: number;
}) {
  const atMax = tabs.length >= maxTabs;

  return (
    <div className="bsdv2-rail bsdv2-rail--tabs">
      <h2 className="bsdv2-rail-sr-title">Scenario Comparison Rail</h2>
      <div className="bsdv2-rail-tabs" role="tablist" aria-label="Saved budget scenarios">
        {tabs.map((t) => {
          const isActive = t.id === activeTabId;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              id={`bsdv2-rail-tab-${t.id}`}
              className={`bsdv2-rail-tab ${isActive ? 'bsdv2-rail-tab--active' : ''}`}
              onClick={() => onSelectTab(t.id)}
            >
              {t.name}
            </button>
          );
        })}
        <button
          type="button"
          className="bsdv2-rail-new"
          onClick={onNewScenario}
          disabled={atMax}
          title={
            atMax
              ? 'Maximum 5 scenarios. Save or remove a scenario before creating another.'
              : 'Create a new unsaved scenario'
          }
        >
          <Plus size={16} strokeWidth={2.25} aria-hidden />
          <span>New Scenario</span>
        </button>
      </div>
    </div>
  );
}
