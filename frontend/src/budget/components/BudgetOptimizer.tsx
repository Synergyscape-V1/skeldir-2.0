import React, { useState, useEffect, useRef } from 'react';
import './budget-optimizer.css';
import { ChevronDown, CheckCheck, XCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { bootstrapAsyncJobRuntime, startBudgetOptimizationJob, subscribeAsyncJobs, type AsyncJob } from '../../lib/asyncJobs';

/* ─── State machine ─── */
const STATES = {
  IDLE: 'idle',
  QUEUED: 'queued',
  RUNNING: 'running',
  RESULTS_READY: 'results_ready',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  ERROR: 'error',
} as const;

type OptimizerState = (typeof STATES)[keyof typeof STATES];

/* ─── Mock data ─── */
interface ChannelAllocation {
  name: string;
  current: string;
  recommended: string;
  delta: string;
  deltaType: 'increase' | 'decrease' | 'neutral';
}

interface OptimizationResult {
  runId: string;
  completionTime: string;
  totalBudget: string;
  summaryText: string;
  channels: ChannelAllocation[];
  confidence: { level: 'HIGH' | 'MEDIUM' | 'LOW'; fillPercent: number };
  impact: { label: string; range: string; note: string };
  reasoning: { step: number; text: string }[];
}

const MOCK_OPTIMIZATION_RESULT: OptimizationResult = {
  runId: 'SK-OPTI-12345',
  completionTime: '2023-10-27 10:45 AM',
  totalBudget: '$50,000',
  summaryText: 'Optimization successful. Spend reallocated for maximum projected revenue.',
  channels: [
    { name: 'Google Search Ads', current: '$22,000', recommended: '$25,500', delta: '+ $3,500', deltaType: 'increase' },
    { name: 'Facebook/Instagram Ads', current: '$18,000', recommended: '$15,200', delta: '- $2,800', deltaType: 'decrease' },
    { name: 'LinkedIn Ads', current: '$6,000', recommended: '$5,800', delta: '- $200', deltaType: 'decrease' },
    { name: 'TikTok Ads', current: '$3,000', recommended: '$3,000', delta: '$0', deltaType: 'neutral' },
    { name: 'Affiliate Marketing', current: '$1,000', recommended: '$500', delta: '- $500', deltaType: 'decrease' },
  ],
  confidence: { level: 'HIGH', fillPercent: 78 },
  impact: {
    label: 'PROJECTED MONTHLY REVENUE IMPACT',
    range: '$152,000 - $168,000',
    note: 'Note: Projection assumes baseline rate of $50,000/month revenue. An e-commerce monthly allocation, for optimization makes contributions or fully projected revenue.',
  },
  reasoning: [
    { step: 1, text: 'Analyzed historical ROAS across all 5 channels over trailing 90 days.' },
    { step: 2, text: 'Identified Google Search Ads as highest-performing channel at 4.2x ROAS.' },
    { step: 3, text: 'Facebook/Instagram Ads showing diminishing returns above $15,200 threshold.' },
    { step: 4, text: 'LinkedIn Ads marginal reduction preserves B2B pipeline with minimal revenue impact.' },
    { step: 5, text: 'Affiliate Marketing reallocation frees capital for higher-leverage channels.' },
    { step: 6, text: 'Projected revenue range calculated at 95% confidence interval.' },
  ],
};

/* ─── Sub-components ─── */

function StatusBadge({ status }: { status: OptimizerState }) {
  if (status !== STATES.RESULTS_READY) return null;
  return (
    <div className="bo-status-badge">
      {/* Match the platform stat's check-circle visual language. */}
      <span aria-hidden="true" className="bo-status-badge__check">
        ✓
      </span>
      Ready for Review
    </div>
  );
}

function BudgetInputPanel({
  state,
  result,
  budgetInput,
  onBudgetChange,
}: {
  state: OptimizerState;
  result: OptimizationResult | null;
  budgetInput: string;
  onBudgetChange: (v: string) => void;
}) {
  const hasResult = ['results_ready', 'approved', 'rejected'].includes(state);

  return (
    <div className="bo-input-panel">
      <h2 className="bo-input-panel__title">Budget Target</h2>
      <div className="bo-input-card">
        <div className="bo-input-card__label">Total Optimized Budget</div>
        {hasResult ? (
          <div className="bo-input-card__value">{result?.totalBudget ?? '$50,000'}</div>
        ) : (
          <input
            type="text"
            className="bo-input-card__input"
            value={budgetInput}
            onChange={(e) => onBudgetChange(e.target.value)}
            placeholder="$50,000"
            disabled={state !== 'idle'}
          />
        )}
      </div>

      {hasResult && result && (
        <div className="bo-summary-card">
          <div className="bo-summary-card__title">Summary</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div className="bo-meta-row">
              <span className="bo-meta-row__label">Optimization Run ID</span>
              <span className="bo-meta-row__value">{result.runId}</span>
            </div>
            <div className="bo-meta-row">
              <span className="bo-meta-row__label">Completion Time</span>
              <span className="bo-meta-row__value">{result.completionTime}</span>
            </div>
          </div>
          <div style={{ marginTop: '12px' }}>
            <div className="bo-summary-text-label">Summary</div>
            <p className="bo-summary-text">{result.summaryText}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function IdleState({ onRunOptimization }: { onRunOptimization: () => void }) {
  return (
    <div className="bo-idle">
      <div className="bo-idle__icon">
        <img
          src="/assets/chart-svgrepo-com.svg"
          alt=""
          width={36}
          height={36}
          style={{ display: "block", objectFit: "contain" }}
        />
      </div>
      <div>
        <h3 className="bo-idle__title">Ready to Optimize</h3>
        <p className="bo-idle__desc">
          Enter your total budget in the panel on the left, then run the optimization engine.
        </p>
      </div>
      <button className="bo-btn-primary" onClick={onRunOptimization}>
        Run Optimization
      </button>
    </div>
  );
}

function SkeletonBar({ width, height = 12, style }: { width: number | string; height?: number; style?: React.CSSProperties }) {
  return <div className="bo-skeleton-bar" style={{ width, height, ...style }} />;
}

function SkeletonLoader({ isRunning, progress = 0 }: { isRunning: boolean; progress: number }) {
  const ROW_WIDTHS = [140, 160, 100, 80, 130];

  return (
    <div className="bo-loading">
      {isRunning && (
        <div className="bo-loading__progress">
          <div className="bo-loading__status">
            <div className="bo-loader-spinner" />
            Optimization running… {Math.round(progress)}%
          </div>
          <div className="bo-progress-track">
            <div className="bo-progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      <div>
        <div className="bo-skeleton-table-header">
          {[80, 60, 80, 50].map((w, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: i > 0 ? 'flex-end' : 'flex-start' }}>
              <SkeletonBar width={w} height={11} />
            </div>
          ))}
        </div>
        {ROW_WIDTHS.map((nameWidth, i) => (
          <div key={i} className="bo-skeleton-table-row">
            <SkeletonBar width={nameWidth} height={13} />
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <SkeletonBar width={60} height={13} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <SkeletonBar width={60} height={13} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <SkeletonBar width={50} height={13} />
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <SkeletonBar width={160} height={12} />
        <SkeletonBar width="100%" height={12} />
      </div>

      <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <SkeletonBar width={220} height={11} />
        <SkeletonBar width={300} height={36} style={{ borderRadius: 'var(--radius-pill)' }} />
        <SkeletonBar width="100%" height={11} />
        <SkeletonBar width="80%" height={11} />
      </div>
    </div>
  );
}

function OptimizationProgressLoader({ secondsRemaining, progress }: { secondsRemaining: number; progress: number }) {
  return (
    <div className="bo-loading">
      <div className="bo-loading__progress">
        <div className="bo-loading__status">
          <div className="bo-loader-spinner" />
          Calculating optimal allocation across 6 channels... {Math.max(0, Math.ceil(secondsRemaining))}s remaining
        </div>
        <div className="bo-progress-track">
          <div className="bo-progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>
    </div>
  );
}

function ChannelAllocationTable({ channels }: { channels: ChannelAllocation[] }) {
  return (
    <div className="bo-table">
      <div className="bo-table-header">
        <div className="bo-table-header__cell">Channel</div>
        <div className="bo-table-header__cell bo-table-header__cell--right">Current</div>
        <div className="bo-table-header__cell bo-table-header__cell--right">Recommended</div>
        <div className="bo-table-header__cell bo-table-header__cell--right">Delta</div>
      </div>
      {channels.map((ch, i) => (
        <div key={i} className="bo-table-row">
          <div className="bo-table-row__name">{ch.name}</div>
          <div className="bo-table-row__current">{ch.current}</div>
          <div className="bo-table-row__recommended">{ch.recommended}</div>
          <div className={`bo-table-row__delta bo-table-row__delta--${ch.deltaType}`}>{ch.delta}</div>
        </div>
      ))}
    </div>
  );
}

function ConfidenceRangeBar({ level, fillPercent }: { level: 'HIGH' | 'MEDIUM' | 'LOW'; fillPercent: number }) {
  const [animatedPoint, setAnimatedPoint] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setAnimatedPoint(fillPercent), 80);
    return () => clearTimeout(t);
  }, [fillPercent]);

  const levelClass = level.toLowerCase();

  // Interpretation:
  // - `fillPercent` is treated as the point estimate position within the 0..100 scale.
  // - The confidence "range" is derived around that point and varies by `level`.
  // - This produces an empty track on both ends with a filled block from lower..upper,
  //   plus a dashed point marker at the estimate position.
  const halfRange =
    level === 'HIGH' ? 10 : level === 'MEDIUM' ? 16 : 22; // percent points

  const clamp = (v: number) => Math.max(0, Math.min(100, v));
  const lowerPercent = clamp(animatedPoint - halfRange);
  const upperPercent = clamp(animatedPoint + halfRange);
  const rangeWidth = Math.max(0, upperPercent - lowerPercent);

  const markerOffsetInRange =
    rangeWidth > 0 ? ((animatedPoint - lowerPercent) / rangeWidth) * 100 : 0;

  return (
    <div className="bo-confidence">
      <div className="bo-confidence__header">
        <span className="bo-confidence__label">Confidence Range Bar</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="bo-confidence__level-label">System Confidence</span>
          <span className={`bo-confidence__level-value bo-confidence__level-value--${levelClass}`}>{level}</span>
        </div>
      </div>
      <div
        className="bo-confidence__track"
        role="progressbar"
        aria-valuenow={fillPercent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`System confidence: ${level} (${fillPercent}%)`}
      >
        <div
          className="bo-confidence__fill"
          style={{
            left: `${lowerPercent}%`,
            width: `${rangeWidth}%`,
          }}
        >
          <div
            className="bo-confidence__point-marker"
            aria-hidden="true"
            style={{ left: `${markerOffsetInRange}%` }}
          />
        </div>
      </div>
      <div className="bo-confidence__sub-labels">
        {['Low Confidence', 'Medium Confidence', 'High Confidence'].map((label) => (
          <span key={label} className="bo-confidence__sub-label">{label}</span>
        ))}
      </div>
    </div>
  );
}

function ReasoningTraceAccordion({ steps }: { steps: { step: number; text: string }[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ flex: 1 }}>
      <button className="bo-reasoning-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <ChevronDown size={16} className={`bo-reasoning-chevron${open ? ' bo-reasoning-chevron--open' : ''}`} />
        Reasoning Trace
      </button>
      <div
        className="bo-reasoning-content"
        style={{ maxHeight: open ? `${steps.length * 52}px` : '0px', marginTop: open ? '12px' : '0px' }}
      >
        <div className="bo-reasoning-steps">
          {steps.map((s) => (
            <div key={s.step} className="bo-reasoning-step">
              <span className="bo-reasoning-step__num">{String(s.step).padStart(2, '0')}</span>
              <span className="bo-reasoning-step__text">{s.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResultsReadyState({
  result,
  onApprove,
  onReject,
  onAddNote,
  noteDraft,
  setNoteDraft,
  auditLog,
}: {
  result: OptimizationResult;
  onApprove: () => void;
  onReject: () => void;
  onAddNote: () => void;
  noteDraft: string;
  setNoteDraft: React.Dispatch<React.SetStateAction<string>>;
  auditLog: Array<{ id: string; atMs: number; action: string; message: string }>;
}) {
  const halfRange =
    result.confidence.level === "HIGH"
      ? 10
      : result.confidence.level === "MEDIUM"
        ? 16
        : 22;

  const clamp = (v: number) => Math.max(0, Math.min(100, v));
  const point = result.confidence.fillPercent;
  const lowerPercent = clamp(point - halfRange);
  const upperPercent = clamp(point + halfRange);

  const parseMoney = (s: string): number => {
    const cleaned = s.replace(/[^0-9.]/g, "");
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : 0;
  };

  const formatMoneyShort = (n: number): string => {
    const abs = Math.abs(n);
    const sign = n < 0 ? "-" : "";
    if (abs >= 1000) return `${sign}$${(abs / 1000).toFixed(1)}K`;
    return `${sign}$${Math.round(abs).toLocaleString("en-US")}`;
  };

  const bucket =
    result.confidence.level === "HIGH"
      ? "narrow"
      : result.confidence.level === "MEDIUM"
        ? "medium"
        : "wide";

  const totalBudgetN = parseMoney(result.totalBudget);
  const likelyLow = totalBudgetN * (lowerPercent / 100);
  const likelyHigh = totalBudgetN * (upperPercent / 100);

  return (
    <div className="bo-results-content">
      <ChannelAllocationTable channels={result.channels} />
      <ConfidenceRangeBar level={result.confidence.level} fillPercent={result.confidence.fillPercent} />
      <div style={{ marginTop: -10, marginBottom: 6, display: "flex", justifyContent: "space-between", gap: 12 }}>
        <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, fontWeight: 400, color: "var(--color-text-secondary)" }}>
          Likely range ({bucket}): <span style={{ fontFamily: "var(--font-data)", fontWeight: 500, color: "var(--color-text-primary)" }}>{formatMoneyShort(likelyLow)}–{formatMoneyShort(likelyHigh)}</span>
        </div>
      </div>
      <div className="bo-impact">
        <div className="bo-impact__label">{result.impact.label}</div>
        <div className="bo-impact__range">{result.impact.range}</div>
        <p className="bo-impact__note">{result.impact.note}</p>
      </div>
      <div className="bo-action-row">
        <ReasoningTraceAccordion steps={result.reasoning} />
        <div className="bo-action-row__buttons">
          <button className="bo-btn-primary" onClick={onApprove} aria-label="Approve budget optimization changes">
            Approve Changes
          </button>
          <button className="bo-btn-reject" onClick={onReject} aria-label="Reject budget optimization changes">
            Reject
          </button>
        </div>
      </div>

      <div style={{ marginTop: 4 }}>
        <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, fontWeight: 500, color: "var(--color-text-primary)", marginBottom: 8 }}>
          Add Note
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <textarea
            value={noteDraft}
            onChange={(e) => setNoteDraft(e.target.value)}
            placeholder="Add feedback or reasoning for approval/rejection..."
            style={{
              flex: 1,
              minHeight: 64,
              resize: "vertical",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border)",
              padding: "10px 12px",
              fontFamily: "var(--font-interface)",
              fontSize: 13,
              color: "var(--color-text-primary)",
              background: "transparent",
              outline: "none",
            }}
          />
          <button className="bo-btn-secondary" onClick={onAddNote} aria-label="Add note to audit log">
            Add Note
          </button>
        </div>

        <div style={{ marginTop: 12 }}>
          <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, fontWeight: 600, color: "var(--color-text-primary)", marginBottom: 8 }}>
            Audit Log
          </div>
          {auditLog.length === 0 ? (
            <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, color: "var(--color-text-secondary)" }}>No actions recorded yet.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {auditLog.map((e) => (
                <div
                  key={e.id}
                  style={{
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-md)",
                    padding: "10px 12px",
                    background: "var(--color-canvas)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                    <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, fontWeight: 600, color: "var(--color-text-primary)", textTransform: "capitalize" }}>
                      {e.action}
                    </div>
                    <div style={{ fontFamily: "var(--font-interface)", fontSize: 11, color: "var(--color-text-tertiary)" }}>
                      {new Date(e.atMs).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </div>
                  </div>
                  <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, color: "var(--color-text-secondary)", marginTop: 4 }}>
                    {e.message}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ConfirmationPanel({
  variant,
  onRunAgain,
  auditLog,
}: {
  variant: "approved" | "rejected";
  onRunAgain: () => void;
  auditLog: Array<{ id: string; atMs: number; action: string; message: string }>;
}) {
  const isApproved = variant === 'approved';

  return (
    <div className="bo-confirmation">
      <div className={`bo-confirmation__icon bo-confirmation__icon--${variant}`}>
        {isApproved ? (
          <CheckCheck size={24} color="var(--status-verified)" />
        ) : (
          <XCircle size={24} color="var(--status-critical)" />
        )}
      </div>
      <div>
        <h3 className="bo-confirmation__title">{isApproved ? 'Changes Approved' : 'Changes Rejected'}</h3>
        <p className="bo-confirmation__desc">
          {isApproved
            ? 'Budget reallocation has been approved and queued for execution.'
            : 'Optimization recommendation has been rejected. No budget changes have been applied.'}
        </p>
      </div>
      <button className="bo-btn-secondary" onClick={onRunAgain}>
        Run New Optimization
      </button>

      {auditLog.length > 0 && (
        <div style={{ width: "100%", marginTop: 16 }}>
          <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, fontWeight: 600, color: "var(--color-text-primary)", marginBottom: 8 }}>
            Audit Log
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {auditLog.map((e) => (
              <div
                key={e.id}
                style={{
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-md)",
                  padding: "10px 12px",
                  background: "var(--color-canvas)",
                }}
              >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, fontWeight: 600, color: "var(--color-text-primary)", textTransform: "capitalize" }}>
                    {e.action}
                  </div>
                  <div style={{ fontFamily: "var(--font-interface)", fontSize: 11, color: "var(--color-text-tertiary)" }}>
                    {new Date(e.atMs).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
                <div style={{ fontFamily: "var(--font-interface)", fontSize: 12, color: "var(--color-text-secondary)", marginTop: 4 }}>
                  {e.message}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ErrorPanel({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="bo-error">
      <div className="bo-error__icon">
        <AlertCircle size={24} color="var(--status-critical)" />
      </div>
      <div>
        <h3 className="bo-error__title">Optimization Failed</h3>
        <p className="bo-error__desc">
          The optimization job encountered an unexpected error. Your budget data has been preserved. Please try again.
        </p>
      </div>
      <button className="bo-btn-retry" onClick={onRetry}>
        <RefreshCw size={14} />
        Retry
      </button>
    </div>
  );
}

/* ─── Main component ─── */
export function BudgetOptimizer() {
  const [optimizerState, setOptimizerState] = useState<OptimizerState>(STATES.IDLE);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [budgetInput, setBudgetInput] = useState('$50,000');
  const [progress, setProgress] = useState(0);
  const [secondsRemaining, setSecondsRemaining] = useState(60);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [resetAtMs, setResetAtMs] = useState<number>(() => {
    if (typeof window === 'undefined') return 0;
    const raw = window.localStorage.getItem('skeldir.budgetOptimizer.resetAtMs.v1');
    const n = raw ? Number(raw) : 0;
    return Number.isFinite(n) ? n : 0;
  });

  type AuditAction = 'approve' | 'reject' | 'note';
  type AuditEntry = { id: string; atMs: number; action: AuditAction; message: string };
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [noteDraft, setNoteDraft] = useState('');

  const lastCompletedJobIdRef = useRef<string | null>(null);
  const optimizerStateRef = useRef<OptimizerState>(optimizerState);
  useEffect(() => {
    optimizerStateRef.current = optimizerState;
  }, [optimizerState]);

  // Short duration so we can test/iterate quickly without waiting.
  const JOB_DURATION_SECONDS = 12;

  const parseMoney = (raw: string): number => {
    const cleaned = raw.replace(/[^0-9.]/g, '');
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : 0;
  };

  const formatMoneyWhole = (n: number): string =>
    `$${Math.round(n).toLocaleString('en-US')}`;

  const parseImpactRange = (range: string): { low: number; high: number } => {
    const nums = [...range.matchAll(/\$([\d,]+)/g)].map((m) => Number((m[1] ?? '').replace(/,/g, '')));
    if (nums.length >= 2) return { low: nums[0], high: nums[1] };
    return { low: 0, high: 0 };
  };

  const formatDelta = (delta: number): { deltaStr: string; deltaType: ChannelAllocation['deltaType'] } => {
    const d = Math.round(delta);
    if (d === 0) return { deltaStr: '$0', deltaType: 'neutral' };
    if (d > 0) return { deltaStr: `+ $${Math.abs(d).toLocaleString('en-US')}`, deltaType: 'increase' };
    return { deltaStr: `- $${Math.abs(d).toLocaleString('en-US')}`, deltaType: 'decrease' };
  };

  const generateResultForBudget = (budgetAmount: number): OptimizationResult => {
    const base = MOCK_OPTIMIZATION_RESULT;
    const baseTotal = parseMoney(base.totalBudget);
    const scale = baseTotal > 0 ? budgetAmount / baseTotal : 1;

    const scaledChannels: ChannelAllocation[] = base.channels.map((ch) => {
      const currentN = parseMoney(ch.current) * scale;
      const recommendedN = parseMoney(ch.recommended) * scale;
      const deltaN = recommendedN - currentN;
      const { deltaStr, deltaType } = formatDelta(deltaN);
      return {
        name: ch.name,
        current: formatMoneyWhole(currentN),
        recommended: formatMoneyWhole(recommendedN),
        delta: deltaStr,
        deltaType,
      };
    });

    const { low, high } = parseImpactRange(base.impact.range);
    const scaledLow = low * scale;
    const scaledHigh = high * scale;

    const now = new Date();
    return {
      ...base,
      runId: `SK-OPTI-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`,
      completionTime: now.toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
      totalBudget: formatMoneyWhole(budgetAmount),
      channels: scaledChannels,
      impact: {
        ...base.impact,
        range: `$${Math.round(scaledLow).toLocaleString('en-US')} - $${Math.round(scaledHigh).toLocaleString('en-US')}`,
      },
    };
  };

  useEffect(() => {
    bootstrapAsyncJobRuntime();

    return subscribeAsyncJobs((jobs: AsyncJob[]) => {
      const state = optimizerStateRef.current;
      if (state === STATES.APPROVED || state === STATES.REJECTED) return;

      const candidateJobs = jobs
        .filter((j) => j.type === "budget_optimization")
        .filter((j) => typeof j.startedAtMs !== "number" || j.startedAtMs >= resetAtMs);

      const job =
        (activeJobId ? candidateJobs.find((j) => j.jobId === activeJobId) : null) ??
        candidateJobs[0];

      if (!job) return;

      const duration = typeof job.durationSeconds === "number" ? job.durationSeconds : JOB_DURATION_SECONDS;
      const remaining = typeof job.timeRemainingSeconds === "number" ? job.timeRemainingSeconds : 0;
      const elapsed = typeof job.elapsedSeconds === "number" ? job.elapsedSeconds : Math.max(0, duration - remaining);
      const nextProgress = duration > 0 ? Math.max(0, Math.min(100, Math.round((elapsed / duration) * 100))) : 0;

      setSecondsRemaining(remaining);
      setProgress(nextProgress);

      if (job.status === "queued") {
        if (state === STATES.IDLE) setOptimizerState(STATES.QUEUED);
      } else if (job.status === "running") {
        if (state === STATES.IDLE || state === STATES.QUEUED) setOptimizerState(STATES.RUNNING);
      } else if (job.status === "complete") {
        if (lastCompletedJobIdRef.current === job.jobId) return;

        const payload = (job.payload ?? {}) as any;
        const budgetAmount =
          typeof payload.budgetAmount === "number"
            ? payload.budgetAmount
            : typeof payload.budgetInput === "string"
              ? parseMoney(payload.budgetInput)
              : parseMoney(budgetInput);

        lastCompletedJobIdRef.current = job.jobId;
        setResult(generateResultForBudget(budgetAmount));
        setOptimizerState(STATES.RESULTS_READY);
        setProgress(100);
      }
    });
  }, [activeJobId, resetAtMs, budgetInput]);

  const handleRunOptimization = () => {
    const newReset = Date.now();
    setResetAtMs(newReset);
    try {
      window.localStorage.setItem('skeldir.budgetOptimizer.resetAtMs.v1', String(newReset));
    } catch {
      // ignore
    }

    setAuditLog([]);
    setNoteDraft('');
    setResult(null);
    setProgress(0);
    setSecondsRemaining(JOB_DURATION_SECONDS);
    lastCompletedJobIdRef.current = null;

    const budgetAmount = parseMoney(budgetInput);
    const jobId = startBudgetOptimizationJob({ budgetInput, budgetAmount, durationSeconds: JOB_DURATION_SECONDS });
    setActiveJobId(jobId);
    setOptimizerState(STATES.QUEUED);
  };

  const handleRetry = () => {
    setResult(null);
    handleRunOptimization();
  };

  const handleApprove = () => {
    setAuditLog((prev) => [
      ...prev,
      { id: `audit_${Date.now()}`, atMs: Date.now(), action: 'approve', message: 'Approved budget optimization changes.' },
    ]);
    setOptimizerState(STATES.APPROVED);
  };

  const handleReject = () => {
    setAuditLog((prev) => [
      ...prev,
      { id: `audit_${Date.now()}`, atMs: Date.now(), action: 'reject', message: 'Rejected budget optimization recommendation.' },
    ]);
    setOptimizerState(STATES.REJECTED);
  };

  const handleRunAgain = () => {
    setResult(null);
    setProgress(0);
    setSecondsRemaining(JOB_DURATION_SECONDS);
    setActiveJobId(null);
    const newReset = Date.now();
    setResetAtMs(newReset);
    try {
      window.localStorage.setItem("skeldir.budgetOptimizer.resetAtMs.v1", String(newReset));
    } catch {
      // ignore
    }
    setAuditLog([]);
    setNoteDraft('');
    lastCompletedJobIdRef.current = null;
    setOptimizerState(STATES.IDLE);
  };

  const isQueued = optimizerState === STATES.QUEUED;
  const isRunning = optimizerState === STATES.RUNNING;
  const isLoading = isQueued || isRunning;

  const panelTitle =
    optimizerState === STATES.IDLE
      ? 'Optimization Results'
      : optimizerState === STATES.APPROVED
        ? 'Approved'
        : optimizerState === STATES.REJECTED
          ? 'Rejected'
          : 'Optimization Results';

  return (
    <div className="bo-root">
      <div className="bo-grid">
        <BudgetInputPanel state={optimizerState} result={result} budgetInput={budgetInput} onBudgetChange={setBudgetInput} />

        <div className="bo-results-rail">
          <div className="bo-rail-header">
            <h2 className="bo-rail-header__title">{panelTitle}</h2>
            <StatusBadge status={optimizerState} />
          </div>

          {optimizerState === STATES.IDLE && <IdleState onRunOptimization={handleRunOptimization} />}
          {isLoading && <OptimizationProgressLoader secondsRemaining={secondsRemaining} progress={progress} />}
          {optimizerState === STATES.RESULTS_READY && result && (
            <ResultsReadyState
              result={result}
              onApprove={handleApprove}
              onReject={handleReject}
              onAddNote={() => {
                const text = noteDraft.trim();
                if (!text) return;
                const now = Date.now();
                setAuditLog((prev) => [...prev, { id: `audit_${now}`, atMs: now, action: 'note', message: text }]);
                setNoteDraft('');
              }}
              noteDraft={noteDraft}
              setNoteDraft={setNoteDraft}
              auditLog={auditLog}
            />
          )}
          {optimizerState === STATES.APPROVED && (
            <ConfirmationPanel variant="approved" onRunAgain={handleRunAgain} auditLog={auditLog} />
          )}
          {optimizerState === STATES.REJECTED && (
            <ConfirmationPanel variant="rejected" onRunAgain={handleRunAgain} auditLog={auditLog} />
          )}
          {optimizerState === STATES.ERROR && <ErrorPanel onRetry={handleRetry} />}
        </div>
      </div>
    </div>
  );
}
