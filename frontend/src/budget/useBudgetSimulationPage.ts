import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LOADING_UNDER_2S_MS } from '../lib/loading/constants';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewBudgetInput } from '../ledger/permissions';
import { ERROR_COPY } from '../lib/copy';
import { generateIdempotencyKey } from '../actions/idempotency';
import { BUDGET_SIMULATION_COPY } from './copy';
import { executeSimulationProposalSubmit } from '../actions/budgetSimulationProposalSubmit';
import { hasActionPermission } from '../actions/permissions';
import {
  BUDGET_CHANNEL_OPTIONS,
  BUDGET_DATE_RANGE_PRESETS,
  BUDGET_DEFAULT_CURRENCY,
  BUDGET_DEFAULT_SPEND_MINOR,
  BUDGET_OBJECTIVE_OPTIONS,
} from './budgetFixtures';
import { getDefaultBudgetInputClient } from './budgetInputClient';
import { getDefaultBudgetSimulationClient } from './budgetSimulationClient';
import { computeSufficiencySummary, isFormEligibleForGeneration } from './budgetSufficiency';
import type {
  BudgetSimulationFormState,
  BudgetSimulationResultDTO,
} from './budgetSimulationTypes';

export type BudgetPagePhase = 'loading' | 'ready' | 'permission_denied' | 'trust_api_error';

export type GeneratePhase = 'idle' | 'loading' | 'success' | 'error';

export type SubmitPhase = 'idle' | 'loading' | 'success' | 'error';

export interface BudgetSimulationPageState {
  pagePhase: BudgetPagePhase;
  form: BudgetSimulationFormState;
  sufficiency: ReturnType<typeof computeSufficiencySummary>;
  generatePhase: GeneratePhase;
  submitPhase: SubmitPhase;
  result: BudgetSimulationResultDTO | null;
  stale: boolean;
  blockedMessage?: string;
  errorMessage?: string;
  toast?: { severity: 'success' | 'error'; message: string };
  inputsLocked: boolean;
  longGenerateLoading: boolean;
}

const DEFAULT_FORM: BudgetSimulationFormState = {
  dateRangeStart: BUDGET_DATE_RANGE_PRESETS[0].start,
  dateRangeEnd: BUDGET_DATE_RANGE_PRESETS[0].end,
  channelIds: BUDGET_CHANNEL_OPTIONS.map((c) => c.id),
  spendConstraintMinor: BUDGET_DEFAULT_SPEND_MINOR,
  currencyCode: BUDGET_DEFAULT_CURRENCY,
  objectiveId: BUDGET_OBJECTIVE_OPTIONS[0].id,
  verifiedRevenueWindowDays: 30,
};

function formSnapshot(form: BudgetSimulationFormState): string {
  return [
    form.dateRangeStart,
    form.dateRangeEnd,
    form.channelIds.join(','),
    form.spendConstraintMinor.toString(),
    form.objectiveId,
    String(form.verifiedRevenueWindowDays),
  ].join('|');
}

export function useBudgetSimulationPage() {
  const navigate = useNavigate();
  const role = getCurrentUserRole();
  const [pagePhase, setPagePhase] = useState<BudgetPagePhase>('loading');
  const [form, setForm] = useState<BudgetSimulationFormState>(DEFAULT_FORM);
  const [generatePhase, setGeneratePhase] = useState<GeneratePhase>('idle');
  const [submitPhase, setSubmitPhase] = useState<SubmitPhase>('idle');
  const [result, setResult] = useState<BudgetSimulationResultDTO | null>(null);
  const [stale, setStale] = useState(false);
  const [blockedMessage, setBlockedMessage] = useState<string>();
  const [errorMessage, setErrorMessage] = useState<string>();
  const [toast, setToast] = useState<{ severity: 'success' | 'error'; message: string }>();
  const [longGenerateLoading, setLongGenerateLoading] = useState(false);
  const generateTimerRef = useRef<number | null>(null);
  const resultSnapshotRef = useRef<string>('');

  const refreshAvailability = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!canViewBudgetInput(role)) {
      setPagePhase('permission_denied');
      return;
    }
    if (!tenant) {
      setPagePhase('trust_api_error');
      setErrorMessage(ERROR_COPY.trustApiReadFailed);
      return;
    }

    const outcome = await getDefaultBudgetInputClient().getBudgetInputAvailability(tenant.tenantId);
    if (outcome.kind === 'permission_denied') {
      setPagePhase('permission_denied');
      return;
    }
    if (outcome.kind === 'trust_api_error') {
      setPagePhase('trust_api_error');
      setErrorMessage(outcome.message);
      return;
    }
    if (outcome.kind === 'blocked_sparse_data') {
      setBlockedMessage(outcome.message);
      setForm((prev) => ({
        ...prev,
        dateRangeStart: outcome.input.dateRangeStart,
        dateRangeEnd: outcome.input.dateRangeEnd,
        channelIds: outcome.input.eligibleChannels,
        spendConstraintMinor: outcome.input.spendConstraintMinor ?? prev.spendConstraintMinor,
        currencyCode: outcome.input.currencyCode,
        objectiveId:
          BUDGET_OBJECTIVE_OPTIONS.find((o) => o.label === outcome.input.objective)?.id ??
          prev.objectiveId,
      }));
    } else if (outcome.kind === 'loaded') {
      setForm((prev) => ({
        ...prev,
        dateRangeStart: outcome.input.dateRangeStart,
        dateRangeEnd: outcome.input.dateRangeEnd,
        channelIds: outcome.input.eligibleChannels.length
          ? outcome.input.eligibleChannels
          : prev.channelIds,
        spendConstraintMinor: outcome.input.spendConstraintMinor ?? prev.spendConstraintMinor,
        currencyCode: outcome.input.currencyCode,
        objectiveId:
          BUDGET_OBJECTIVE_OPTIONS.find((o) => o.label === outcome.input.objective)?.id ??
          prev.objectiveId,
      }));
    }
    setPagePhase('ready');
  }, [role]);

  useEffect(() => {
    void refreshAvailability();
  }, [refreshAvailability]);

  const sufficiency = useMemo(
    () =>
      computeSufficiencySummary(form, {
        loading: generatePhase === 'loading',
        error: pagePhase === 'trust_api_error',
        policyBlocked: blockedMessage?.includes('policy') ?? false,
        trustApiOperational: pagePhase !== 'trust_api_error',
      }),
    [form, generatePhase, pagePhase, blockedMessage],
  );

  const inputsLocked = generatePhase === 'loading' || submitPhase === 'loading';

  const patchForm = useCallback(
    (patch: Partial<BudgetSimulationFormState>) => {
      setForm((prev) => {
        const next = { ...prev, ...patch };
        const snapshot = formSnapshot(next);
        if (result && snapshot !== resultSnapshotRef.current) {
          setStale(true);
        }
        return next;
      });
    },
    [result],
  );

  const generateSimulation = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant || !isFormEligibleForGeneration(sufficiency)) return;

    setGeneratePhase('loading');
    setToast(undefined);
    setLongGenerateLoading(false);
    if (generateTimerRef.current) window.clearTimeout(generateTimerRef.current);
    generateTimerRef.current = window.setTimeout(() => setLongGenerateLoading(true), LOADING_UNDER_2S_MS);

    const outcome = await getDefaultBudgetSimulationClient().generateSimulation(tenant.tenantId, form);

    if (generateTimerRef.current) {
      window.clearTimeout(generateTimerRef.current);
      generateTimerRef.current = null;
    }
    setLongGenerateLoading(false);

    if (outcome.kind === 'success') {
      setResult(outcome.result);
      resultSnapshotRef.current = formSnapshot(form);
      setStale(false);
      setGeneratePhase('success');
      setToast({
        severity: 'success',
        message: BUDGET_SIMULATION_COPY.toast.generateSuccess,
      });
      return;
    }

    setGeneratePhase('error');
    setToast({
      severity: 'error',
      message:
        outcome.kind === 'blocked_sparse_data'
          ? outcome.message
          : BUDGET_SIMULATION_COPY.toast.generateError,
    });
  }, [form, sufficiency]);

  const submitProposal = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant || !result || stale) return;
    if (!hasActionPermission(role, 'submit_budget_proposal')) {
      setSubmitPhase('error');
      setToast({ severity: 'error', message: ERROR_COPY.permissionDenied });
      return;
    }
    if (result.policyAuthority === 'blocked' || result.policyAuthority === 'simulation_only') {
      setSubmitPhase('error');
      setToast({ severity: 'error', message: BUDGET_SIMULATION_COPY.toast.submitError });
      return;
    }
    if (result.auditArtifactStatus !== 'written') {
      setSubmitPhase('error');
      setToast({ severity: 'error', message: 'Audit artifact is not ready. Proposal submission is unavailable until audit status is written.' });
      return;
    }

    setSubmitPhase('loading');
    const key = generateIdempotencyKey(
      tenant.tenantId,
      'budget_simulation',
      result.simulationId,
      'submit_proposal',
    );
    const outcome = await executeSimulationProposalSubmit(
      tenant.tenantId,
      result.simulationId,
      result.versionStamp,
      key,
    );

    if (outcome.status === 'success') {
      setSubmitPhase('success');
      setToast({ severity: 'success', message: BUDGET_SIMULATION_COPY.submit.successToast });
      navigate(`/app/budget/${result.simulationId}`);
      return;
    }

    setSubmitPhase('error');
    setToast({
      severity: 'error',
      message: outcome.safeUserCopy ?? 'Proposal submission failed. No platform action was taken.',
    });
  }, [navigate, result, role, stale]);

  const dismissToast = useCallback(() => setToast(undefined), []);

  return {
    pagePhase,
    form,
    patchForm,
    sufficiency,
    generatePhase,
    submitPhase,
    result,
    stale,
    blockedMessage,
    errorMessage,
    toast,
    inputsLocked,
    longGenerateLoading,
    generateSimulation,
    submitProposal,
    dismissToast,
    refreshAvailability,
    canGenerate: isFormEligibleForGeneration(sufficiency) && pagePhase === 'ready',
    canSubmit:
      Boolean(result) &&
      !stale &&
      generatePhase === 'success' &&
      submitPhase !== 'loading' &&
      result?.policyAuthority !== 'blocked' &&
      result?.policyAuthority !== 'simulation_only' &&
      result?.auditArtifactStatus === 'written',
  };
}
