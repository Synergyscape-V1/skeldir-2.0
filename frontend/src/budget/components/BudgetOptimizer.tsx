import React, { useMemo, useState } from "react";
import { InvestigationStatePanel } from "../../components/llm/InvestigationStatePanel";
import { useBudgetCentaurController } from "../../components/llm/useBudgetCentaurController";
import "./budget-optimizer.css";
import "../../components/llm/llm-control.css";

type OptimizationGoal = "maximize_roas" | "maximize_revenue" | "minimize_cpa";

function formatMoney(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function GoalSelect({
  goal,
  onChange,
}: {
  goal: OptimizationGoal;
  onChange: (nextGoal: OptimizationGoal) => void;
}) {
  return (
    <label className="bo-input-card">
      <span className="bo-input-card__label">Optimization Goal</span>
      <select
        className="bo-input-card__input"
        value={goal}
        onChange={(event) => onChange(event.target.value as OptimizationGoal)}
      >
        <option value="maximize_roas">Maximize ROAS</option>
        <option value="maximize_revenue">Maximize Revenue</option>
        <option value="minimize_cpa">Minimize CPA</option>
      </select>
    </label>
  );
}

export function BudgetOptimizer() {
  const {
    isSubmitting,
    jobId,
    snapshot,
    authorityRecommendation,
    synthesis,
    pendingAction,
    requestError,
    mutationResponse,
    submitOptimization,
    runMutation,
    refreshResult,
  } = useBudgetCentaurController();

  const [budgetInput, setBudgetInput] = useState("50000");
  const [goal, setGoal] = useState<OptimizationGoal>("maximize_roas");
  const [reviewNote, setReviewNote] = useState("");

  const allocations = authorityRecommendation?.allocations ?? [];
  const evidence = authorityRecommendation?.evidence ?? [];

  const hasDeterministicAuthority = allocations.length > 0 || evidence.length > 0;
  const hasSynthesis = Boolean(synthesis?.non_authoritative_summary);

  const canSubmit = useMemo(() => {
    const parsed = Number(budgetInput);
    return Number.isFinite(parsed) && parsed >= 1000;
  }, [budgetInput]);

  return (
    <div className="bo-root">
      <div className="bo-grid">
        <section className="bo-input-panel">
          <h2 className="bo-input-panel__title">Budget Optimization Request</h2>
          <label className="bo-input-card">
            <span className="bo-input-card__label">Total Budget (USD)</span>
            <input
              className="bo-input-card__input"
              inputMode="numeric"
              value={budgetInput}
              onChange={(event) => setBudgetInput(event.target.value.replace(/[^\d.]/g, ""))}
            />
          </label>
          <GoalSelect goal={goal} onChange={setGoal} />
          <button
            className="bo-btn-primary"
            disabled={isSubmitting || !canSubmit}
            onClick={() => void submitOptimization(Number(budgetInput), goal)}
          >
            {isSubmitting ? "Submitting..." : "Start Asynchronous Recommendation"}
          </button>
          <p className="bo-impact__note">
            This surface is async by design. Machine compute and reviewer decision
            are separate lifecycle states.
          </p>
          {jobId ? (
            <p className="bo-impact__note">
              Active Job ID: <code>{jobId}</code>
            </p>
          ) : null}
        </section>

        <section className="bo-results-rail">
          {snapshot ? (
            <InvestigationStatePanel
              title="Budget Lifecycle"
              snapshot={snapshot}
              pendingAction={pendingAction}
              onAction={(action) => void runMutation(action, reviewNote)}
              errorMessage={requestError}
            />
          ) : (
            <div className="bo-idle">
              <h3 className="bo-idle__title">No active budget job</h3>
              <p className="bo-idle__desc">
                Submit a request to begin deterministic analysis and reviewer-gated
                lifecycle transitions.
              </p>
            </div>
          )}

          {snapshot ? (
            <label className="bo-input-card" style={{ marginTop: 12 }}>
              <span className="bo-input-card__label">Review Note / Reason</span>
              <textarea
                className="bo-input-card__input"
                rows={3}
                value={reviewNote}
                onChange={(event) => setReviewNote(event.target.value)}
                placeholder="Optional rationale for approve/reject/refine decisions."
              />
            </label>
          ) : null}

          {mutationResponse ? (
            <div className="llm-synthesis-card" style={{ marginTop: 12 }}>
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
            </div>
          ) : null}

          {hasDeterministicAuthority ? (
            <div className="llm-authority-card" style={{ marginTop: 12 }}>
              <h3 className="llm-authority-card__title">
                Deterministic Recommendation (Authoritative)
              </h3>
              <p className="llm-authority-card__subtitle">
                Rendered from typed deterministic fields only.
              </p>
              <table className="llm-authority-table">
                <thead>
                  <tr>
                    <th>Channel</th>
                    <th>Current Budget</th>
                    <th>Recommended Budget</th>
                    <th>Delta Budget</th>
                    <th>Expected ROAS</th>
                  </tr>
                </thead>
                <tbody>
                  {allocations.map((allocation) => (
                    <tr key={allocation.channel}>
                      <td>{allocation.channel}</td>
                      <td>{formatMoney(allocation.current_budget)}</td>
                      <td>{formatMoney(allocation.recommended_budget)}</td>
                      <td>{formatMoney(allocation.delta_budget)}</td>
                      <td>{allocation.expected_roas.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {evidence.length > 0 ? (
                <ol className="llm-evidence-list">
                  {evidence.map((point, index) => (
                    <li key={`${point.metric_name}-${point.channel}-${index}`}>
                      {point.metric_name} ({point.channel}) = {point.metric_value} from{" "}
                      {point.source_table}
                    </li>
                  ))}
                </ol>
              ) : null}
              <button className="bo-btn-secondary" onClick={() => void refreshResult()}>
                Refresh Full Result Payload
              </button>
            </div>
          ) : null}

          {hasSynthesis ? (
            <div className="llm-synthesis-card" style={{ marginTop: 12 }}>
              <h3 className="llm-synthesis-card__title">
                LLM Synthesis (Non-Authoritative)
              </h3>
              <p className="llm-synthesis-card__subtitle">
                This text is explanatory only and cannot override deterministic
                authority fields.
              </p>
              <p>{synthesis?.non_authoritative_summary}</p>
              {synthesis?.caveats?.length ? (
                <ul className="llm-synthesis-list">
                  {synthesis.caveats.map((caveat, index) => (
                    <li key={`${caveat}-${index}`}>{caveat}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
