import { IconCalendar } from '../../icons/StatusIcons';

import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';

import {

  BUDGET_CHANNEL_OPTIONS,

  BUDGET_DATE_RANGE_PRESETS,

  BUDGET_OBJECTIVE_OPTIONS,

  BUDGET_REVENUE_WINDOW_OPTIONS,

} from '../../../budget/budgetFixtures';

import type { BudgetSimulationFormState } from '../../../budget/budgetSimulationTypes';

import { formatMoneyMinorDisplayWithCents } from '../../../lib/money';

import { SufficiencyGateSummary } from '../SufficiencyGateSummary/SufficiencyGateSummary';

import type { SufficiencySummary } from '../../../budget/budgetSimulationTypes';

import shared from '../../../styles/shared.module.css';

import styles from './BudgetSimulationInputCard.module.css';



export interface BudgetSimulationInputCardProps {

  form: BudgetSimulationFormState;

  sufficiency: SufficiencySummary;

  disabled?: boolean;

  onPatch: (patch: Partial<BudgetSimulationFormState>) => void;

}



export function BudgetSimulationInputCard({

  form,

  sufficiency,

  disabled = false,

  onPatch,

}: BudgetSimulationInputCardProps) {

  const datePresetValue = `${form.dateRangeStart}|${form.dateRangeEnd}`;



  const toggleChannel = (channelId: string) => {

    const next = form.channelIds.includes(channelId)

      ? form.channelIds.filter((id) => id !== channelId)

      : [...form.channelIds, channelId];

    onPatch({ channelIds: next });

  };



  return (

    <section

      className={styles.card}

      aria-labelledby="budget-simulation-inputs-heading"

      data-simulation-input-card

      data-budget-elevated-panel="true"

    >

      <h2 id="budget-simulation-inputs-heading" className={styles.srOnly}>

        {BUDGET_SIMULATION_COPY.inputSectionLabel}

      </h2>



      <div className={styles.fieldGrid}>

        <label className={styles.field}>

          <span className={styles.fieldLabel}>

            <IconCalendar className={styles.fieldIcon} aria-hidden />

            {BUDGET_SIMULATION_COPY.fields.dateRange}

          </span>

          <select

            className={[styles.control, shared.focusVisible].join(' ')}

            value={datePresetValue}

            disabled={disabled}

            aria-required="true"

            onChange={(e) => {

              const [start, end] = e.target.value.split('|');

              onPatch({ dateRangeStart: start, dateRangeEnd: end });

            }}

          >

            {BUDGET_DATE_RANGE_PRESETS.map((preset) => (

              <option key={preset.id} value={`${preset.start}|${preset.end}`}>

                {preset.label}

              </option>

            ))}

          </select>

        </label>



        <label className={styles.field}>

          <span className={styles.fieldLabel}>

            {BUDGET_SIMULATION_COPY.fields.spendConstraint}

          </span>

          <input

            className={[styles.control, shared.focusVisible].join(' ')}

            type="text"

            inputMode="numeric"

            disabled={disabled}

            aria-required="true"

            value={formatMoneyMinorDisplayWithCents(form.spendConstraintMinor, form.currencyCode)}

            onChange={(e) => {

              const digits = e.target.value.replace(/[^\d]/g, '');

              if (!digits) return;

              onPatch({ spendConstraintMinor: BigInt(digits) });

            }}

          />

        </label>



        <label className={styles.field}>

          <span className={styles.fieldLabel}>

            {BUDGET_SIMULATION_COPY.fields.objective}

          </span>

          <select

            className={[styles.control, shared.focusVisible].join(' ')}

            value={form.objectiveId}

            disabled={disabled}

            aria-required="true"

            onChange={(e) => onPatch({ objectiveId: e.target.value })}

          >

            {BUDGET_OBJECTIVE_OPTIONS.map((option) => (

              <option key={option.id} value={option.id}>

                {option.label}

              </option>

            ))}

          </select>

        </label>



        <label className={styles.field}>
          <span className={styles.fieldLabel}>
            {BUDGET_SIMULATION_COPY.fields.verifiedRevenueWindow}
          </span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={form.verifiedRevenueWindowDays}
            disabled={disabled}
            aria-required="true"
            onChange={(e) => onPatch({ verifiedRevenueWindowDays: Number.parseInt(e.target.value, 10) })}
          >
            {BUDGET_REVENUE_WINDOW_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>



      <div className={styles.fullWidthField}>

        <span className={styles.fieldLabel}>

          {BUDGET_SIMULATION_COPY.fields.channelsIncluded}

        </span>

        <div className={styles.chipRow} aria-label={BUDGET_SIMULATION_COPY.fields.channelsIncluded}>

          <div className={styles.chips} role="list">

            {BUDGET_CHANNEL_OPTIONS.map((channel) => {

              const selected = form.channelIds.includes(channel.id);

              if (selected) {

                return (

                  <span key={channel.id} className={styles.chip} role="listitem">

                    <span>{channel.label}</span>

                    <button

                      type="button"

                      className={[styles.chipRemove, shared.focusVisible].join(' ')}

                      disabled={disabled}

                      aria-label={`Remove ${channel.label}`}

                      onClick={() => toggleChannel(channel.id)}

                    >

                      ×

                    </button>

                  </span>

                );

              }

              return (

                <button

                  key={channel.id}

                  type="button"

                  className={[styles.chipOption, shared.focusVisible].join(' ')}

                  disabled={disabled}

                  aria-pressed={false}

                  aria-label={channel.label}

                  onClick={() => toggleChannel(channel.id)}

                >

                  {channel.label}

                </button>

              );

            })}

          </div>

        </div>

      </div>



      <SufficiencyGateSummary summary={sufficiency} variant="inset" />

    </section>

  );

}


