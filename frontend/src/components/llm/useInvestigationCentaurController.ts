import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createInvestigationsApiClient,
  separateInvestigationResultPayload,
  separateInvestigationResultResponse,
  type CreateInvestigationAcceptedResponse,
  type CreateInvestigationRequest,
  type InvestigationMutationRequest,
  type InvestigationMutationResponse,
  type InvestigationResultResponse,
  type InvestigationStatusResponse,
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

type InvestigationMutationAction =
  InvestigationStatusResponse["available_actions"][number];

function mutationRequiresBody(action: InvestigationMutationAction): boolean {
  return action === "reject" || action === "refine";
}

function buildMutationPayload(
  action: InvestigationMutationAction,
  reasonOrNote: string,
): InvestigationMutationRequest | undefined {
  const trimmed = reasonOrNote.trim();
  if (!trimmed && !mutationRequiresBody(action)) {
    return undefined;
  }
  if (!trimmed) {
    return {};
  }
  return { reason: trimmed, note: trimmed };
}

export interface UseInvestigationCentaurControllerState {
  isSubmitting: boolean;
  investigationId: string | null;
  snapshot: CentaurLifecycleSnapshot | null;
  authorityFindings: InvestigationResultResponse["deterministic_findings"] | null;
  synthesis: InvestigationResultResponse["llm_synthesis"] | undefined | null;
  pendingAction: InvestigationMutationAction | null;
  mutationIssue: CentaurMutationIssue | null;
  requestError: string | null;
  mutationResponse: InvestigationMutationResponse | null;
  submitInvestigation: (question: string) => Promise<void>;
  runMutation: (
    action: InvestigationMutationAction,
    reasonOrNote: string,
  ) => Promise<void>;
  setInvestigationId: (investigationId: string | null) => void;
}

export function useInvestigationCentaurController(): UseInvestigationCentaurControllerState {
  const [launchResponse, setLaunchResponse] =
    useState<CreateInvestigationAcceptedResponse | null>(null);
  const [statusResponse, setStatusResponse] =
    useState<InvestigationStatusResponse | null>(null);
  const [resultResponse, setResultResponse] =
    useState<InvestigationResultResponse | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] =
    useState<InvestigationMutationAction | null>(null);
  const [mutationIssue, setMutationIssue] = useState<CentaurMutationIssue | null>(
    null,
  );
  const [mutationResponse, setMutationResponse] =
    useState<InvestigationMutationResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [manualInvestigationId, setManualInvestigationId] = useState<string | null>(
    null,
  );

  const hydrationStateRef = useRef<{
    investigationId: string | null;
    lastHydratedStatus: InvestigationStatusResponse["status"] | null;
  }>({
    investigationId: null,
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
    llmInvestigationsBaseUrl?: string;
    centaurAuthorization?: string;
  } }).__SKELDIR_RUNTIME_CONFIG__;
  const baseUrl =
    runtimeConfig?.llmInvestigationsBaseUrl ?? "http://localhost:4024";
  const authorization = runtimeConfig?.centaurAuthorization;
  const client = useMemo(() => createInvestigationsApiClient(baseUrl), [baseUrl]);

  const investigationId =
    launchResponse?.investigation_id ?? manualInvestigationId ?? null;

  const fetchStatus = useCallback(
    async (targetInvestigationId: string) => {
      const next = await client.getInvestigationStatus(targetInvestigationId, {
        correlationId: createStableUuid(),
        authorization,
      });
      setStatusResponse(next);
    },
    [authorization, client],
  );

  const refreshResult = useCallback(
    async (targetInvestigationId: string) => {
      const next = await client.getInvestigationResult(targetInvestigationId, {
        correlationId: createStableUuid(),
        authorization,
      });
      setResultResponse(next);
    },
    [authorization, client],
  );

  useEffect(() => {
    if (!investigationId) {
      clearMutationAttemptState(mutationAttemptRef.current);
      return;
    }
    let cancelled = false;

    const pollStatus = async () => {
      try {
        await fetchStatus(investigationId);
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
  }, [fetchStatus, investigationId]);

  useEffect(() => {
    if (!investigationId || !statusResponse) {
      return;
    }

    if (hydrationStateRef.current.investigationId !== investigationId) {
      hydrationStateRef.current = {
        investigationId,
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
    void refreshResult(investigationId).catch((error) => {
      setRequestError(error instanceof Error ? error.message : String(error));
    });
  }, [investigationId, refreshResult, statusResponse]);

  const submitInvestigation = useCallback(
    async (question: string) => {
      const trimmedQuestion = question.trim();
      if (trimmedQuestion.length < 10) {
        setRequestError("Question must be at least 10 characters.");
        return;
      }

      setIsSubmitting(true);
      setRequestError(null);
      setStatusResponse(null);
      setResultResponse(null);
      setMutationResponse(null);
      setMutationIssue(null);
      clearMutationAttemptState(mutationAttemptRef.current);

      try {
        const payload: CreateInvestigationRequest = { question: trimmedQuestion };
        const next = await client.createInvestigation(payload, {
          correlationId: createStableUuid(),
          authorization,
        });
        setLaunchResponse(next);
        setManualInvestigationId(null);
        hydrationStateRef.current = {
          investigationId: next.investigation_id,
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
    async (action: InvestigationMutationAction, reasonOrNote: string) => {
      if (!investigationId || !statusResponse) {
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

        let response: InvestigationMutationResponse;
        switch (action) {
          case "approve":
            response = await client.approveInvestigation(
              investigationId,
              payload,
              headers,
            );
            break;
          case "reject":
            response = await client.rejectInvestigation(
              investigationId,
              payload,
              headers,
            );
            break;
          case "refine":
            response = await client.refineInvestigation(
              investigationId,
              payload,
              headers,
            );
            break;
          case "rerun":
            response = await client.rerunInvestigation(
              investigationId,
              payload,
              headers,
            );
            break;
          case "retry":
            response = await client.retryInvestigation(
              investigationId,
              payload,
              headers,
            );
            break;
          case "cancel":
            response = await client.cancelInvestigation(
              investigationId,
              payload,
              headers,
            );
            break;
          default:
            response = await client.cancelInvestigation(
              investigationId,
              payload,
              headers,
            );
            break;
        }

        setMutationResponse(response);
        setMutationIssue(null);
        clearMutationAttemptState(mutationAttemptRef.current);
        await fetchStatus(investigationId);
        if (isResultReadyStatus(response.status)) {
          await refreshResult(investigationId);
        }
      } catch (error) {
        const issue = mapMutationErrorToIssue(error);
        setMutationIssue(issue);
        setRequestError(`${issue.title}: ${issue.detail}`);
      } finally {
        setPendingAction(null);
      }
    },
    [authorization, client, fetchStatus, investigationId, refreshResult, statusResponse],
  );

  const snapshot = useMemo<CentaurLifecycleSnapshot | null>(() => {
    if (!launchResponse && !statusResponse && !manualInvestigationId) {
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
  }, [launchResponse, manualInvestigationId, statusResponse]);

  const authorityFindings = useMemo(() => {
    if (resultResponse) {
      return separateInvestigationResultResponse(resultResponse).authority
        .deterministic_findings;
    }
    if (statusResponse?.result_preview) {
      return separateInvestigationResultPayload(statusResponse.result_preview).authority
        .deterministic_findings;
    }
    return null;
  }, [resultResponse, statusResponse?.result_preview]);

  const synthesis = useMemo(() => {
    if (resultResponse) {
      return separateInvestigationResultResponse(resultResponse).synthesis;
    }
    if (statusResponse?.result_preview) {
      return separateInvestigationResultPayload(statusResponse.result_preview).synthesis;
    }
    return null;
  }, [resultResponse, statusResponse?.result_preview]);

  const setInvestigationId = useCallback((nextInvestigationId: string | null) => {
    setManualInvestigationId(nextInvestigationId);
    if (nextInvestigationId === null) {
      setLaunchResponse(null);
      setStatusResponse(null);
      setResultResponse(null);
      setMutationResponse(null);
      setMutationIssue(null);
      clearMutationAttemptState(mutationAttemptRef.current);
    }
  }, []);

  return {
    isSubmitting,
    investigationId,
    snapshot,
    authorityFindings,
    synthesis,
    pendingAction,
    mutationIssue,
    requestError,
    mutationResponse,
    submitInvestigation,
    runMutation,
    setInvestigationId,
  };
}
