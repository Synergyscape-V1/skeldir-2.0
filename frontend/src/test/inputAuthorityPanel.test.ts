import { describe, expect, it } from 'vitest';
import { BUDGET_SUFFICIENCY_THRESHOLDS } from '../budget/budgetFixtures';
import { BUDGET_SIMULATION_COPY } from '../budget/copy';
import { resolveInputAuthorityPresentation } from '../budget/inputAuthorityPanel';
import type { SufficiencySummary } from '../budget/budgetSimulationTypes';

function summary(state: SufficiencySummary['state'], rows: SufficiencySummary['rows'] = []): SufficiencySummary {
  return { state, rows };
}

describe('resolveInputAuthorityPresentation', () => {
  it('eligible state uses success tone and generate-allowed facts', () => {
    const presentation = resolveInputAuthorityPresentation(summary('eligible'), 5, 842, true);
    expect(presentation.panelTone).toBe('eligible');
    expect(presentation.chipTone).toBe('success');
    expect(presentation.statusLabel).toBe(BUDGET_SIMULATION_COPY.inputAuthority.eligible);
    expect(presentation.facts).toEqual(
      expect.arrayContaining([
        { term: 'Action authority', detail: 'Generate simulation allowed' },
        { term: 'Deterministic evidence present', detail: 'Yes' },
      ]),
    );
  });

  it('blocked state uses threshold facts and blocked action authority', () => {
    const presentation = resolveInputAuthorityPresentation(summary('blocked'), 2, 120, true);
    expect(presentation.panelTone).toBe('blocked');
    expect(presentation.chipTone).toBe('error');
    expect(presentation.facts).toEqual([
      {
        term: 'Minimum channels required',
        detail: String(BUDGET_SUFFICIENCY_THRESHOLDS.minimumChannels),
      },
      { term: 'Channels available', detail: '2' },
      {
        term: 'Minimum verified conversions required',
        detail: String(BUDGET_SUFFICIENCY_THRESHOLDS.minimumVerifiedConversions),
      },
      { term: 'Verified conversions available', detail: '120' },
      { term: 'Action authority', detail: 'blocked' },
    ]);
  });

  it('partial state uses warning tone while keeping generate allowed', () => {
    const presentation = resolveInputAuthorityPresentation(summary('partial'), 5, 842, true);
    expect(presentation.panelTone).toBe('partial');
    expect(presentation.chipTone).toBe('warning');
    expect(presentation.statusLabel).toBe(BUDGET_SIMULATION_COPY.inputAuthority.statusPartial);
    expect(presentation.facts.find((fact) => fact.term === 'Action authority')?.detail).toBe(
      'Generate simulation allowed',
    );
  });
});
