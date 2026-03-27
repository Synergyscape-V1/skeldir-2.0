import React from "react";
import {
  describeCentaurLifecycle,
  formatIsoDateTime,
  isReviewRailVisible,
  type CentaurLifecycleSnapshot,
  type CentaurMutationIssue,
  type CentaurMutationAction,
} from "./controlPlane";
import "./llm-control.css";

const ACTION_LABELS: Record<CentaurMutationAction, string> = {
  approve: "Approve",
  reject: "Reject",
  refine: "Request Refine",
  rerun: "Request Rerun",
  retry: "Retry",
  cancel: "Cancel",
};

interface InvestigationStatePanelProps {
  title: string;
  snapshot: CentaurLifecycleSnapshot;
  pendingAction: CentaurMutationAction | null;
  onAction: (action: CentaurMutationAction) => void;
  mutationIssue?: CentaurMutationIssue | null;
  errorMessage?: string | null;
}

export function InvestigationStatePanel({
  title,
  snapshot,
  pendingAction,
  onAction,
  mutationIssue,
  errorMessage,
}: InvestigationStatePanelProps) {
  const descriptor = describeCentaurLifecycle(snapshot);
  const showReviewRail = isReviewRailVisible(snapshot);
  const reviewOnlyActions: CentaurMutationAction[] = ["approve", "reject", "refine"];
  const nonReviewActions = snapshot.availableActions.filter(
    (action) => !reviewOnlyActions.includes(action),
  );
  const progress =
    typeof snapshot.progressPercentage === "number"
      ? Math.max(0, Math.min(100, snapshot.progressPercentage))
      : null;

  return (
    <section className="llm-state-panel" data-tone={descriptor.tone}>
      <header className="llm-state-panel__header">
        <div>
          <p className="llm-state-panel__label">{title}</p>
          <h2 className="llm-state-panel__title">{descriptor.title}</h2>
          <p className="llm-state-panel__detail">{descriptor.detail}</p>
        </div>
        <div className="llm-state-panel__meta">
          <span className="llm-state-panel__meta-row">
            Last Updated: {formatIsoDateTime(snapshot.lastUpdated)}
          </span>
          <span className="llm-state-panel__meta-row">
            Freshness Seconds:{" "}
            {typeof snapshot.dataFreshnessSeconds === "number"
              ? snapshot.dataFreshnessSeconds
              : "n/a"}
          </span>
          <span className="llm-state-panel__meta-row">
            Step: {snapshot.currentStep ?? "n/a"}
          </span>
        </div>
      </header>

      {progress !== null && (
        <div
          className="llm-state-panel__progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <div className="llm-state-panel__progress-fill" style={{ width: `${progress}%` }} />
        </div>
      )}

      {typeof snapshot.estimatedDurationSeconds === "number" && (
        <p className="llm-state-panel__duration">
          Estimated Duration (contract): {snapshot.estimatedDurationSeconds}s
        </p>
      )}

      {snapshot.status === "failed" && (
        <p className="llm-state-panel__terminal">
          Failure reason: {snapshot.failure?.reason ?? "n/a"}
        </p>
      )}
      {snapshot.status === "timeout" && (
        <p className="llm-state-panel__terminal">
          Timeout reason: {snapshot.failure?.reason ?? "n/a"}
        </p>
      )}
      {snapshot.status === "cancelled" && (
        <p className="llm-state-panel__terminal">
          Cancelled reason: {snapshot.failure?.reason ?? "n/a"}
        </p>
      )}
      {snapshot.status === "rejected" && (
        <p className="llm-state-panel__terminal">
          Output rejected; rerun/refine actions remain contract-governed.
        </p>
      )}
      {snapshot.status === "refine_requested" && (
        <p className="llm-state-panel__terminal">
          Refinement requested; awaiting recompute transition.
        </p>
      )}
      {snapshot.status === "rerun_requested" && (
        <p className="llm-state-panel__terminal">
          Rerun requested; machine workflow will re-enter compute states.
        </p>
      )}

      {showReviewRail && (
        <div className="llm-state-panel__actions">
          {snapshot.availableActions.map((action) => (
            <button
              key={action}
              className="llm-state-panel__action"
              onClick={() => onAction(action)}
              disabled={pendingAction !== null}
              data-action={action}
            >
              {pendingAction === action ? "Submitting..." : ACTION_LABELS[action]}
            </button>
          ))}
        </div>
      )}

      {!showReviewRail && nonReviewActions.length > 0 && (
        <div className="llm-state-panel__actions">
          {nonReviewActions.map((action) => (
            <button
              key={action}
              className="llm-state-panel__action"
              onClick={() => onAction(action)}
              disabled={pendingAction !== null}
              data-action={action}
            >
              {pendingAction === action ? "Submitting..." : ACTION_LABELS[action]}
            </button>
          ))}
        </div>
      )}

      {mutationIssue ? (
        <div
          className="llm-state-panel__error"
          data-mutation-issue-kind={mutationIssue.kind}
        >
          <strong>{mutationIssue.title}</strong>
          <p>{mutationIssue.detail}</p>
          <p>{mutationIssue.retryable ? "Retryable mutation issue." : "Non-retryable mutation issue."}</p>
        </div>
      ) : null}
      {!mutationIssue && errorMessage ? (
        <p className="llm-state-panel__error">{errorMessage}</p>
      ) : null}
    </section>
  );
}
