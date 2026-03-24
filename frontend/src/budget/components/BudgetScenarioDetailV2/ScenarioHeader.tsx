import React from 'react';
import { CheckCircle } from 'lucide-react';

interface Scenario {
  name: string;
  proposedTotalBudget: string;
  projectedTotalRevenue: string;
  projectedROI: string;
}

export function ScenarioHeader({ scenario }: { scenario: Scenario }) {
  return (
    <header className="bsdv2-scenario-topbar" aria-label="Budget scenario">
      <div className="bsdv2-scenario-topbar-left">
        <h1 className="bsdv2-scenario-topbar-title">Budget Scenario Detail</h1>
        <span className="bsdv2-scenario-topbar-sep" aria-hidden>
          ·
        </span>
        <span className="bsdv2-scenario-topbar-name" title={scenario.name}>
          {scenario.name}
        </span>
        <span className="bsdv2-scenario-topbar-badge">Active scenario</span>
      </div>
      <div className="bsdv2-scenario-topbar-right">
        <div className="bsdv2-scenario-topbar-kpis" role="group" aria-label="Scenario projections">
          <div className="bsdv2-scenario-topbar-kpi">
            <div className="bsdv2-scenario-topbar-kpi-label">Proposed total budget</div>
            <div className="bsdv2-scenario-topbar-kpi-value">{scenario.proposedTotalBudget}</div>
          </div>
          <div className="bsdv2-scenario-topbar-kpi">
            <div className="bsdv2-scenario-topbar-kpi-label">Projected total revenue</div>
            <div className="bsdv2-scenario-topbar-kpi-value">{scenario.projectedTotalRevenue}</div>
          </div>
          <div className="bsdv2-scenario-topbar-kpi">
            <div className="bsdv2-scenario-topbar-kpi-label">Projected ROI</div>
            <div className="bsdv2-scenario-topbar-kpi-value">{scenario.projectedROI}</div>
          </div>
        </div>
        <div className="bsdv2-scenario-topbar-verified">
          <CheckCircle size={14} strokeWidth={2.25} aria-hidden />
          Verified
        </div>
      </div>
    </header>
  );
}
