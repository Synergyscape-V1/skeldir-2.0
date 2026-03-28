import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { InvestigationStatePanel } from "../components/llm/InvestigationStatePanel";
import { useInvestigationCentaurController } from "../components/llm/useInvestigationCentaurController";
import "../components/llm/llm-control.css";

export function InvestigationConsole() {
  const { investigationId: routeInvestigationId } = useParams();
  const {
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
  } = useInvestigationCentaurController();

  const [question, setQuestion] = useState("");
  const [reviewNote, setReviewNote] = useState("");

  useEffect(() => {
    if (routeInvestigationId) {
      setInvestigationId(routeInvestigationId);
    }
  }, [routeInvestigationId, setInvestigationId]);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <section className="llm-authority-card">
        <h2 className="llm-authority-card__title">Investigation Request</h2>
        <p className="llm-authority-card__subtitle">
          No synchronous financial chat. Start an async investigation and review
          deterministic findings before any decision.
        </p>
        <textarea
          rows={4}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Example: Why did CTR decline week-over-week across paid channels?"
          style={{
            width: "100%",
            border: "1px solid var(--border-default)",
            borderRadius: 10,
            padding: "10px 12px",
            fontSize: 14,
            resize: "vertical",
            boxSizing: "border-box",
          }}
        />
        <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
          <button
            className="bo-btn-primary"
            disabled={isSubmitting || question.trim().length < 10}
            onClick={() => void submitInvestigation(question)}
          >
            {isSubmitting ? "Submitting..." : "Submit Investigation"}
          </button>
          <button
            className="bo-btn-secondary"
            onClick={() => {
              setQuestion("");
              setReviewNote("");
              setInvestigationId(null);
            }}
          >
            Reset
          </button>
        </div>
        {investigationId ? (
          <p className="llm-authority-card__subtitle" style={{ marginTop: 8 }}>
            Active Investigation ID: <code>{investigationId}</code>
          </p>
        ) : null}
        {!snapshot && requestError ? (
          <p className="llm-state-panel__error" style={{ marginTop: 8 }}>
            {requestError}
          </p>
        ) : null}
      </section>

      {snapshot ? (
        <InvestigationStatePanel
          title="Investigation Lifecycle"
          snapshot={snapshot}
          pendingAction={pendingAction}
          onAction={(action) => void runMutation(action, reviewNote)}
          mutationIssue={mutationIssue}
          errorMessage={requestError}
        />
      ) : null}

      {snapshot ? (
        <section className="llm-synthesis-card">
          <h3 className="llm-synthesis-card__title">Review Note / Reason</h3>
          <textarea
            rows={3}
            value={reviewNote}
            onChange={(event) => setReviewNote(event.target.value)}
            placeholder="Optional note for approve/reject/refine/rerun/retry/cancel mutation calls."
            style={{
              width: "100%",
              border: "1px solid var(--border-default)",
              borderRadius: 10,
              padding: "10px 12px",
              fontSize: 14,
              resize: "vertical",
              boxSizing: "border-box",
            }}
          />
        </section>
      ) : null}

      {mutationResponse ? (
        <section className="llm-synthesis-card">
          <h3 className="llm-synthesis-card__title">Last Mutation</h3>
          <p className="llm-synthesis-card__subtitle">
            Action: {mutationResponse.action} | Status: {mutationResponse.status}
          </p>
          <p className="llm-synthesis-card__subtitle">
            Idempotency key: <code>{mutationResponse.idempotency_key}</code>
          </p>
          <p className="llm-synthesis-card__subtitle">
            Replay: {mutationResponse.idempotency_replayed ? "true" : "false"}
          </p>
        </section>
      ) : null}

      {authorityFindings && authorityFindings.length > 0 ? (
        <section className="llm-authority-card">
          <h3 className="llm-authority-card__title">
            Deterministic Findings (Authoritative)
          </h3>
          <p className="llm-authority-card__subtitle">
            Rendered from deterministic typed fields only.
          </p>
          <ol className="llm-evidence-list">
            {authorityFindings.map((finding) => (
              <li key={finding.finding_id}>
                <strong>{finding.title}</strong> [{finding.severity}] confidence{" "}
                {finding.deterministic_confidence_score.toFixed(2)}
                {finding.evidence.length > 0 ? (
                  <ul className="llm-synthesis-list">
                    {finding.evidence.map((point, index) => (
                      <li
                        key={`${finding.finding_id}-${point.metric_name}-${index}`}
                      >
                        {point.metric_name}: {point.metric_value}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {synthesis?.non_authoritative_summary ? (
        <section className="llm-synthesis-card">
          <h3 className="llm-synthesis-card__title">
            LLM Synthesis (Non-Authoritative)
          </h3>
          <p className="llm-synthesis-card__subtitle">
            Explanatory narrative only. It does not provide decision authority.
          </p>
          <p>{synthesis.non_authoritative_summary}</p>
          {synthesis.caveats?.length ? (
            <ul className="llm-synthesis-list">
              {synthesis.caveats.map((caveat, index) => (
                <li key={`${caveat}-${index}`}>{caveat}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
