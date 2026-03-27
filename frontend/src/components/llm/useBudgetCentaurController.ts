import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createBudgetApiClient,
  separateBudgetRecommendationResponse,
  separateBudgetResultPayload,
  type BudgetMutationRequest,
  type BudgetMutationResponse,
  type BudgetRecommendationResponse,
  type BudgetStatusResponse,
  type CreateBudgetOptimizationAcceptedResponse,
  type CreateBudgetOptimizationRequest,
} from "../../api/contracts";
import {
  clearMutationAttemptState,
  createMutationAttemptFingerprint,
  createStableUuid,
  isResultReadyStatus,
  mapMutationErrorToIssue,
  resolveAttemptIdempotencyKey,
  type CentaurMutationIssue,
  type CentaurLifecycleSnapshot,
} from "./controlPlane";

const STATUS_POLL_INTERVAL_MS = 5000;

type BudgetMutationAction = BudgetStatusResponse["available_actions"][number];

function mutationRequiresBody(action: BudgetMutationAction): boolean {
  return action === "reject" || action === "refine";
}

function buildMutationPayload(
  action: BudgetMutationAction,
  reasonOrNote: string,
): BudgetMutationRequest | undefined {
  const trimmed = reasonOrNote.trim();
  if (!trimmed && !mutationRequiresBody(action)) {
    return undefined;
  }
  if (!trimmed) {
    return {};
  }
  return { reason: trimmed, note: trimmed };
}

function mapLaunchToCreatePayload(
  totalBudget: number,
  goal: CreateBudgetOptimizationRequest["optimization_goal"],
): CreateBudgetOptimizationRequest {
  return {
    total_budget: totalBudget,
    optimization_goal: goal,
  };
}

export interface UseBudgetCentaurControllerState {
  isSubmitting: boolean;
  jobId: string | null;
  snapshot: CentaurLifecycleSnapshot | null;
  authorityRecommendation:
    | BudgetRecommendationResponse["deterministic_recommendation"]
    | null;
  synthesis:
    | BudgetRecommendationResponse["llm_synthesis"]
    | undefined
    | null;
  pendingAction: BudgetMutationAction | null;
  mutationIssue: CentaurMutationIssue | null;
  requestError: string | null;
  mutationResponse: BudgetMutationResponse | null;
  submitOptimization: (
    totalBudget: number,
    goal: CreateBudgetOptimizationRequest["optimization_goal"],
  ) => Promise<void>;
  runMutation: (
    action: BudgetMutationAction,
    reasonOrNote: string,
  ) => Promise<void>;
  refreshResult: () => Promise<void>;
}

export function useBudgetCentaurController(): UseBudgetCentaurControllerState {
  const [launchResponse, setLaunchResponse] =
    useState<CreateBudgetOptimizationAcceptedResponse | null>(null);
  const [statusResponse, setStatusResponse] = useState<BudgetStatusResponse | null>(
    null,
  );
  const [resultResponse, setResultResponse] =
    useState<BudgetRecommendationResponse | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<BudgetMutationAction | null>(
    null,
  );
  const [mutationIssue, setMutationIssue] = useState<CentaurMutationIssue | null>(
    null,
  );
  const [mutationResponse, setMutationResponse] =
    useState<BudgetMutationResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const hydrationStateRef = useRef<{
    jobId: string | null;
    lastHydratedStatus: BudgetStatusResponse["status"] | null;
  }>({
    jobId: null,
    lastHydratedStatus: null,
  });
  const mutationAttemptRef = useRef<{
    fingerprint: string | null;
    idempotencyKey: string | null;
  }>({
    fingerprint: null,
    idempotencyKey: null,
  });

  const runtimeConfig = (globalThis as { __SKELDIR_RUNTIME_CONFIG__?: {
    llmBudgetBaseUrl?: string;
    centaurAuthorization?: string;
  } }).__SKELDIR_RUNTIME_CONFIG__;
  const baseUrl = runtimeConfig?.llmBudgetBaseUrl ?? "http://localhost:4025";
  const authorization = runtimeConfig?.centaurAuthorization;

  const client = useMemo(() => createBudgetApiClient(baseUrl), [baseUrl]);
  const jobId = launchResponse?.job_id ?? null;

  const fetchStatus = useCallback(
    async (currentJobId: string) => {
      const next = await client.getBudgetRecommendationStatus(currentJobId, {
        correlationId: createStableUuid(),
        authorization,
      });
      setStatusResponse(next);
    },
    [authorization, client],
  );

  const refreshResult = useCallback(async () => {
    if (!jobId) {
      clearMutationAttemptState(mutationAttemptRef.current);
      return;
    }
    const next = await client.getBudgetRecommendation(jobId, {
      correlationId: createStableUuid(),
      authorization,
    });
    setResultResponse(next);
  }, [authorization, client, jobId]);

  useEffect(() => {
    if (!jobId) {
      return;
    }
    let cancelled = false;

    const pollStatus = async () => {
      try {
        await fetchStatus(jobId);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setRequestError(error instanceof Error ? error.message : String(error));
      }
    };

    void pollStatus();
    const timer = window.setInterval(() => {
      void pollStatus();
    }, STATUS_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [fetchStatus, jobId]);

  useEffect(() => {
    if (!jobId || !statusResponse) {
      return;
    }

    if (hydrationStateRef.current.jobId !== jobId) {
      hydrationStateRef.current = {
        jobId,
        lastHydratedStatus: null,
      };
    }

    if (!isResultReadyStatus(statusResponse.status)) {
      return;
    }
    if (hydrationStateRef.current.lastHydratedStatus === statusResponse.status) {
      return;
    }

    hydrationStateRef.current.lastHydratedStatus = statusResponse.status;
    void refreshResult().catch((error) => {
      setRequestError(error instanceof Error ? error.message : String(error));
    });
  }, [jobId, refreshResult, statusResponse]);

  const submitOptimization = useCallback(
    async (
      totalBudget: number,
      goal: CreateBudgetOptimizationRequest["optimization_goal"],
    ) => {
      setIsSubmitting(true);
      setRequestError(null);
      setStatusResponse(null);
      setResultResponse(null);
      setMutationResponse(null);
      setMutationIssue(null);
      clearMutationAttemptState(mutationAttemptRef.current);
      try {
        const payload = mapLaunchToCreatePayload(totalBudget, goal);
        const next = await client.createBudgetOptimization(payload, {
          correlationId: createStableUuid(),
          authorization,
        });
        setLaunchResponse(next);
        hydrationStateRef.current = {
          jobId: next.job_id,
          lastHydratedStatus: null,
        };
        clearMutationAttemptState(mutationAttemptRef.current);
      } catch (error) {
        setRequestError(error instanceof Error ? error.message : String(error));
      } finally {
        setIsSubmitting(false);
      }
    },
    [authorization, client],
  );

  const runMutation = useCallback(
    async (action: BudgetMutationAction, reasonOrNote: string) => {
      if (!jobId || !statusResponse) {
        return;
      }

      setPendingAction(action);
      setRequestError(null);
      setMutationIssue(null);
      try {
        const attemptFingerprint = createMutationAttemptFingerprint(
          action,
          reasonOrNote,
        );
        const idempotencyKey = resolveAttemptIdempotencyKey(
          mutationAttemptRef.current,
          attemptFingerprint,
        );
        const headers = {
          correlationId: createStableUuid(),
          authorization,
          idempotencyKey: idempotencyKey,
        };
        const payload = buildMutationPayload(action, reasonOrNote);

        let response: BudgetMutationResponse;
        switch (action) {
          case "approve":
            response = await client.approveBudgetRecommendation(jobId, payload, headers);
            break;
          case "reject":
            response = await client.rejectBudgetRecommendation(jobId, payload, headers);
            break;
          case "refine":
            response = await client.refineBudgetRecommendation(jobId, payload, headers);
            break;
          case "rerun":
            response = await client.rerunBudgetRecommendation(jobId, payload, headers);
            break;
          case "retry":
            response = await client.retryBudgetRecommendation(jobId, payload, headers);
            break;
          case "cancel":
            response = await client.cancelBudgetRecommendation(jobId, payload, headers);
            break;
          default:
            response = await client.cancelBudgetRecommendation(jobId, payload, headers);
            break;
        }

        setMutationResponse(response);
        setMutationIssue(null);
        clearMutationAttemptState(mutationAttemptRef.current);
        await fetchStatus(jobId);
        if (isResultReadyStatus(response.status)) {
          await refreshResult();
        }
      } catch (error) {
        const issue = mapMutationErrorToIssue(error);
        setMutationIssue(issue);
        setRequestError(`${issue.title}: ${issue.detail}`);
      } finally {
        setPendingAction(null);
      }
    },
    [authorization, client, fetchStatus, jobId, refreshResult, statusResponse],
  );

  const snapshot = useMemo<CentaurLifecycleSnapshot | null>(() => {
    if (!launchResponse && !statusResponse) {
      return null;
    }

    const fallbackStatus = launchResponse?.status ?? "submitted";

    return {
      status: statusResponse?.status ?? fallbackStatus,
      progressPercentage: statusResponse?.progress_percentage,
      currentStep: statusResponse?.current_step,
      reviewRequired: statusResponse?.review_required ?? false,
      availableActions: statusResponse?.available_actions ?? [],
      estimatedDurationSeconds: launchResponse?.estimated_duration_seconds,
      dataFreshnessSeconds: statusResponse?.data_freshness_seconds,
      lastUpdated: statusResponse?.last_updated,
      failure: statusResponse?.failure,
    };
  }, [launchResponse, statusResponse]);

  const authorityRecommendation = useMemo(() => {
    if (resultResponse) {
      return separateBudgetRecommendationResponse(resultResponse).authority
        .deterministic_recommendation;
    }
    if (statusResponse?.result_preview) {
      return separateBudgetResultPayload(statusResponse.result_preview).authority
        .deterministic_recommendation;
    }
    return null;
  }, [resultResponse, statusResponse?.result_preview]);

  const synthesis = useMemo(() => {
    if (resultResponse) {
      return separateBudgetRecommendationResponse(resultResponse).synthesis;
    }
    if (statusResponse?.result_preview) {
      return separateBudgetResultPayload(statusResponse.result_preview).synthesis;
    }
    return null;
  }, [resultResponse, statusResponse?.result_preview]);

  return {
    isSubmitting,
    jobId,
    snapshot,
    authorityRecommendation,
    synthesis,
    pendingAction,
    mutationIssue,
    requestError,
    mutationResponse,
    submitOptimization,
    runMutation,
    refreshResult,
  };
}
