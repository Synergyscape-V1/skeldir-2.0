import { BUDGET_SIMULATION_COPY } from './copy';
import { BUDGET_SUFFICIENCY_THRESHOLDS } from './budgetFixtures';
import type {
  BudgetSimulationFormState,
  SufficiencyGateRow,
  SufficiencySummary,
} from './budgetSimulationTypes';

export function computeSufficiencySummary(
  form: BudgetSimulationFormState,
  options: {
    loading?: boolean;
    error?: boolean;
    policyBlocked?: boolean;
    trustApiOperational?: boolean;
  } = {},
): SufficiencySummary {
  if (options.error) {
    return { state: 'error', rows: [] };
  }

  if (options.loading) {
    return { state: 'loading', rows: buildGateRows(form, options) };
  }

  const hasRequiredInputs =
    form.dateRangeStart &&
    form.dateRangeEnd &&
    form.channelIds.length > 0 &&
    form.spendConstraintMinor > 0n &&
    form.objectiveId &&
    form.verifiedRevenueWindowDays > 0;

  if (!hasRequiredInputs) {
    return { state: 'empty', rows: [] };
  }

  const rows = buildGateRows(form, options);
  const channelsPass = form.channelIds.length >= BUDGET_SUFFICIENCY_THRESHOLDS.minimumChannels;
  const conversionsPass =
    BUDGET_SUFFICIENCY_THRESHOLDS.fixtureVerifiedConversions >=
    BUDGET_SUFFICIENCY_THRESHOLDS.minimumVerifiedConversions;
  const policyPass = !options.policyBlocked;
  const allPass = channelsPass && conversionsPass && policyPass && options.trustApiOperational !== false;

  if (!allPass) {
    return { state: 'blocked', rows };
  }

  return { state: 'eligible', rows };
}

function buildGateRows(
  form: BudgetSimulationFormState,
  options: { policyBlocked?: boolean },
): SufficiencyGateRow[] {
  const { minimumChannels, minimumVerifiedConversions, fixtureVerifiedConversions } =
    BUDGET_SUFFICIENCY_THRESHOLDS;
  const channelsPass = form.channelIds.length >= minimumChannels;
  const conversionsPass = fixtureVerifiedConversions >= minimumVerifiedConversions;

  return [
    {
      id: 'minimum_channels',
      label: BUDGET_SIMULATION_COPY.gates.minimumChannels,
      status: channelsPass ? 'passed' : 'failed',
      detail: `${form.channelIds.length} selected / ${minimumChannels} required`,
    },
    {
      id: 'verified_conversions',
      label: BUDGET_SIMULATION_COPY.gates.verifiedConversions,
      status: conversionsPass ? 'passed' : 'failed',
      detail: `${fixtureVerifiedConversions} / ${minimumVerifiedConversions} required`,
    },
    {
      id: 'verified_revenue_window',
      label: BUDGET_SIMULATION_COPY.gates.verifiedRevenueWindow,
      status: form.verifiedRevenueWindowDays > 0 ? 'passed' : 'failed',
      detail: `${form.verifiedRevenueWindowDays} days selected`,
    },
    {
      id: 'policy_checks',
      label: BUDGET_SIMULATION_COPY.gates.policyChecks,
      status: options.policyBlocked ? 'failed' : 'passed',
      detail: options.policyBlocked ? BUDGET_SIMULATION_COPY.gates.failed : '',
    },
    {
      id: 'supplemental_evidence',
      label: BUDGET_SIMULATION_COPY.gates.supplementalEvidence,
      status: 'available',
      detail: '',
    },
  ];
}

export function isFormEligibleForGeneration(summary: SufficiencySummary): boolean {
  return summary.state === 'eligible';
}
