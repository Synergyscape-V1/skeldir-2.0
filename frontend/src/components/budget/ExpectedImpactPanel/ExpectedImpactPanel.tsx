import { PolicyImpactCard } from '../PolicyImpactCard/PolicyImpactCard';
import type { BudgetSimulationResultDTO } from '../../../budget/budgetSimulationTypes';

export interface ExpectedImpactPanelProps {
  result: BudgetSimulationResultDTO;
}

export function ExpectedImpactPanel({ result }: ExpectedImpactPanelProps) {
  return (
    <div data-expected-impact-panel data-budget-elevated-panel="true">
      <PolicyImpactCard result={result} />
    </div>
  );
}


