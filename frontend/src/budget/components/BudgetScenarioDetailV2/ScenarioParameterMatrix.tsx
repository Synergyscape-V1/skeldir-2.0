import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ChannelLogo } from './ChannelLogos';
import {
  MATRIX_CHANNEL_ROWS,
  MATRIX_HORIZON_OPTIONS,
  MATRIX_MODEL_OPTIONS,
  MATRIX_SCENARIO_OPTIONS,
  type MatrixParametersSnapshot,
} from './scenarioData';

function parseCurrencyInput(raw: string): number {
  const n = Number(String(raw).replace(/[^0-9.]/g, ''));
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

function formatCurrency(n: number): string {
  return `$${Math.round(n).toLocaleString('en-US')}`;
}

/** When one channel's % changes, scale the others so the total stays 100%. */
function redistributePercents(
  prev: Record<string, number>,
  changedId: string,
  newPct: number
): Record<string, number> {
  const ids = Object.keys(prev);
  const clamped = Math.max(0, Math.min(100, newPct));
  const others = ids.filter((id) => id !== changedId);
  const oldOthersSum = others.reduce((s, id) => s + prev[id], 0);
  const remaining = 100 - clamped;
  const next: Record<string, number> = { ...prev, [changedId]: clamped };

  if (others.length === 0) return next;

  if (oldOthersSum <= 0) {
    const each = remaining / others.length;
    others.forEach((id) => {
      next[id] = each;
    });
  } else {
    others.forEach((id) => {
      next[id] = (prev[id] / oldOthersSum) * remaining;
    });
  }

  const sum = ids.reduce((s, id) => s + next[id], 0);
  const drift = 100 - sum;
  if (Math.abs(drift) > 0.0001 && others.length) {
    next[others[others.length - 1]] = (next[others[others.length - 1]] ?? 0) + drift;
  }
  return next;
}

function buildSnapshot(
  scenarioName: string,
  totalBudget: number,
  percents: Record<string, number>,
  model: string,
  horizon: string
): MatrixParametersSnapshot {
  return { scenarioName, totalBudget, percents: { ...percents }, model, horizon };
}

export function ScenarioParameterMatrix({
  value,
  onChange,
  savedSnapshot,
  onSave,
  onParametersChange,
  debounceMs = 320,
}: {
  value: MatrixParametersSnapshot;
  onChange: (next: MatrixParametersSnapshot) => void;
  savedSnapshot: MatrixParametersSnapshot;
  onSave: () => void;
  onParametersChange?: (snapshot: MatrixParametersSnapshot) => void;
  debounceMs?: number;
}) {
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const scenarioNameOptions = useMemo(() => {
    const base: string[] = [...MATRIX_SCENARIO_OPTIONS];
    if (!base.includes(value.scenarioName)) base.push(value.scenarioName);
    return base;
  }, [value.scenarioName]);

  const totalBudgetStr = useMemo(
    () => value.totalBudget.toLocaleString('en-US'),
    [value.totalBudget]
  );

  const channelAmounts = useMemo(() => {
    const out: Record<string, number> = {};
    MATRIX_CHANNEL_ROWS.forEach((row) => {
      out[row.id] = (value.totalBudget * (value.percents[row.id] ?? 0)) / 100;
    });
    return out;
  }, [value.totalBudget, value.percents]);

  useEffect(() => {
    if (!onParametersChange) return;
    const t = window.setTimeout(() => {
      onParametersChange(
        buildSnapshot(value.scenarioName, value.totalBudget, value.percents, value.model, value.horizon)
      );
    }, debounceMs);
    return () => window.clearTimeout(t);
  }, [value, debounceMs, onParametersChange]);

  const handleTotalBudgetChange = useCallback(
    (raw: string) => {
      const n = parseCurrencyInput(raw);
      onChange({ ...value, totalBudget: n });
    },
    [onChange, value]
  );

  const handlePercentChange = useCallback(
    (id: string, raw: string) => {
      const n = Number.parseFloat(raw);
      if (!Number.isFinite(n)) return;
      onChange({
        ...value,
        percents: redistributePercents(value.percents, id, n),
      });
    },
    [onChange, value]
  );

  const handleSliderChange = useCallback(
    (id: string, pct: number) => {
      onChange({
        ...value,
        percents: redistributePercents(value.percents, id, pct),
      });
    },
    [onChange, value]
  );

  const handleSave = useCallback(() => {
    onSave();
    setSaveMessage('Scenario saved locally. Connect to API to persist.');
    window.setTimeout(() => setSaveMessage(null), 4000);
  }, [onSave]);

  const handleReset = useCallback(() => {
    onChange({
      ...savedSnapshot,
      percents: { ...savedSnapshot.percents },
    });
  }, [onChange, savedSnapshot]);

  return (
    <div className="bsdv2-panel bsdv2-panel--matrix bsdv2-matrix-form">
      <div className="bsdv2-panel-header">
        <h2 className="bsdv2-panel-title">Scenario Parameter Matrix</h2>
      </div>

      <div className="bsdv2-matrix-form__body" role="region" aria-label="Scenario parameters">
        <div className="bsdv2-matrix-field">
          <label className="bsdv2-matrix-field__label" htmlFor="bsdv2-matrix-scenario">
            Scenario Name
          </label>
          <div className="bsdv2-matrix-select-wrap">
            <select
              id="bsdv2-matrix-scenario"
              className="bsdv2-matrix-select"
              value={value.scenarioName}
              onChange={(e) => onChange({ ...value, scenarioName: e.target.value })}
            >
              {scenarioNameOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="bsdv2-matrix-field">
          <label className="bsdv2-matrix-field__label" htmlFor="bsdv2-matrix-total">
            Total Budget
          </label>
          <div className="bsdv2-matrix-currency-input">
            <span className="bsdv2-matrix-currency-input__prefix" aria-hidden>
              $
            </span>
            <input
              id="bsdv2-matrix-total"
              type="text"
              inputMode="numeric"
              className="bsdv2-matrix-input bsdv2-matrix-input--mono"
              value={totalBudgetStr}
              onChange={(e) => handleTotalBudgetChange(e.target.value)}
              aria-describedby="bsdv2-matrix-total-hint"
            />
          </div>
          <p id="bsdv2-matrix-total-hint" className="bsdv2-matrix-field__hint">
            Adjusting total updates channel amounts from the current allocation %.
          </p>
        </div>

        <div className="bsdv2-matrix-section-rule" aria-hidden />
        <h3 className="bsdv2-matrix-section-title">Allocation (by channel)</h3>

        <div className="bsdv2-matrix-scroll bsdv2-matrix-scroll--allocation">
          {MATRIX_CHANNEL_ROWS.map((row) => {
            const pct = value.percents[row.id] ?? 0;
            const amount = channelAmounts[row.id] ?? 0;
            return (
              <div key={row.id} className="bsdv2-matrix-allocation-row">
                <div className="bsdv2-matrix-allocation-row__header">
                  <div className="bsdv2-channel-cell">
                    <ChannelLogo id={row.logo} />
                    <span className="bsdv2-matrix-channel-name">{row.name}</span>
                  </div>
                  <div className="bsdv2-matrix-allocation-row__pct">
                    <input
                      type="number"
                      className="bsdv2-matrix-input bsdv2-matrix-input--pct"
                      min={0}
                      max={100}
                      step={0.1}
                      value={Math.round(pct * 1000) / 1000}
                      onChange={(e) => handlePercentChange(row.id, e.target.value)}
                      aria-label={`${row.name} allocation percent`}
                    />
                    <span className="bsdv2-matrix-pct-suffix">%</span>
                  </div>
                </div>
                <div className="bsdv2-matrix-allocation-row__amount" aria-live="polite">
                  {formatCurrency(amount)}
                </div>
                <input
                  type="range"
                  className="bsdv2-matrix-slider"
                  min={0}
                  max={100}
                  step={0.1}
                  value={pct}
                  onChange={(e) => handleSliderChange(row.id, Number(e.target.value))}
                  aria-label={`${row.name} allocation slider`}
                />
              </div>
            );
          })}
        </div>

        <div className="bsdv2-matrix-section-rule" aria-hidden />
        <h3 className="bsdv2-matrix-section-title">Confidence settings</h3>

        <div className="bsdv2-matrix-field">
          <label className="bsdv2-matrix-field__label" htmlFor="bsdv2-matrix-model">
            Model
          </label>
          <div className="bsdv2-matrix-select-wrap">
            <select
              id="bsdv2-matrix-model"
              className="bsdv2-matrix-select"
              value={value.model}
              onChange={(e) => onChange({ ...value, model: e.target.value })}
            >
              {MATRIX_MODEL_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="bsdv2-matrix-field">
          <label className="bsdv2-matrix-field__label" htmlFor="bsdv2-matrix-horizon">
            Forecast Horizon
          </label>
          <div className="bsdv2-matrix-select-wrap">
            <select
              id="bsdv2-matrix-horizon"
              className="bsdv2-matrix-select"
              value={value.horizon}
              onChange={(e) => onChange({ ...value, horizon: e.target.value })}
            >
              {MATRIX_HORIZON_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="bsdv2-matrix-section-rule" aria-hidden />
        <div className="bsdv2-matrix-actions">
          <button type="button" className="bsdv2-matrix-btn bsdv2-matrix-btn--primary" onClick={handleSave}>
            Save
          </button>
          <button type="button" className="bsdv2-matrix-btn bsdv2-matrix-btn--secondary" onClick={handleReset}>
            Reset
          </button>
        </div>

        {saveMessage ? (
          <p className="bsdv2-matrix-save-msg" role="status">
            {saveMessage}
          </p>
        ) : null}
      </div>
    </div>
  );
}
