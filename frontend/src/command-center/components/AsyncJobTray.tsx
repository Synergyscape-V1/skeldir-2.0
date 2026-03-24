import React, { useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Check, Loader2, XCircle } from 'lucide-react';
import {
  cancelAsyncJob,
  retryAsyncJob,
  type AsyncJob,
  type AsyncJobStatus,
} from '../../lib/asyncJobs';

function shortAgo(msDelta: number): string {
  const s = Math.max(0, Math.floor(msDelta / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function formatStarted(job: AsyncJob): string | null {
  if (!job.startedAtMs) return null;
  return `Started ${shortAgo(Date.now() - job.startedAtMs)} ago`;
}

function formatCompleted(job: AsyncJob): string | null {
  const t = job.completedAtMs ?? job.startedAtMs;
  if (!t) return null;
  return `Completed ${shortAgo(Date.now() - t)} ago`;
}

function resultRoute(job: AsyncJob): string {
  switch (job.type) {
    case 'budget_optimization':
      return '/budget';
    case 'data_backfill':
      return '/channels/meta';
    case 'attribution_refresh':
      return '/command-center';
    case 'sync':
      return '/channels/google_ads';
    default:
      return '/command-center';
  }
}

function progressPercent(job: AsyncJob): number {
  const max = job.durationSeconds ?? job.maxDurationSeconds ?? 60;
  if (job.status === 'complete') return 100;
  if (job.status === 'queued') return 0;
  if (job.status === 'running') {
    const elapsed = job.elapsedSeconds ?? 0;
    return Math.min(100, Math.round((elapsed / max) * 100));
  }
  if (job.status === 'timeout' || job.status === 'error') return 100;
  return 0;
}

/** Completed jobs: same `Check` 16×16 / stroke 2 as Trust Band `FreshnessIcon` (fresh). */
function PhaseIcon({ status }: { status: AsyncJobStatus }) {
  const trustBandCheck = { size: 16 as const, strokeWidth: 2 as const, 'aria-hidden': true as const };
  if (status === 'running') {
    return <Loader2 className="cc-async-job__icon cc-async-job__icon--spin" size={18} aria-hidden />;
  }
  if (status === 'complete') {
    return <Check {...trustBandCheck} className="cc-async-job__icon cc-async-job__icon--ok" />;
  }
  if (status === 'timeout') {
    return <AlertTriangle className="cc-async-job__icon cc-async-job__icon--warn" size={18} aria-hidden />;
  }
  if (status === 'error') {
    return <XCircle className="cc-async-job__icon cc-async-job__icon--err" size={18} aria-hidden />;
  }
  /* queued */
  return <span className="cc-async-job__dot-queued" aria-hidden />;
}

function ProgressTrack({
  job,
  variant,
}: {
  job: AsyncJob;
  variant: 'brand' | 'success' | 'warn' | 'error' | 'muted';
}) {
  const pct = progressPercent(job);
  return (
    <div className={`cc-async-job__track cc-async-job__track--${variant}`} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="cc-async-job__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function AsyncJobCard({ job }: { job: AsyncJob }) {
  const navigate = useNavigate();

  const onView = useCallback(() => {
    navigate(resultRoute(job));
  }, [job, navigate]);

  const onCopyId = useCallback(() => {
    const id = job.correlationId ?? job.jobId;
    if (navigator.clipboard?.writeText) void navigator.clipboard.writeText(id);
  }, [job.correlationId, job.jobId]);

  const remaining = job.timeRemainingSeconds;
  const statusLine = job.statusMessage ?? '';

  const showCancel = job.status === 'queued' || job.status === 'running';
  const showRetry = job.status === 'timeout' || job.status === 'error';
  const showView = job.status === 'complete';

  return (
    <div className="cc-async-job">
      <div className="cc-async-job__top">
        <div className="cc-async-job__title-row">
          <PhaseIcon status={job.status} />
          <span className="cc-async-job__title">{job.label}</span>
        </div>
        {(showCancel || showRetry) && (
          <div className="cc-async-job__actions">
            {showCancel && (
              <button type="button" className="cc-async-job__btn cc-async-job__btn--ghost" onClick={() => cancelAsyncJob(job.jobId)}>
                Cancel
              </button>
            )}
            {showRetry && (
              <>
                <button type="button" className="cc-async-job__btn cc-async-job__btn--ghost" onClick={() => retryAsyncJob(job.jobId)}>
                  Retry
                </button>
                <a className="cc-async-job__btn cc-async-job__btn--ghost" href={`mailto:support@skeldir.com?subject=Async%20job%20${encodeURIComponent(job.jobId)}`}>
                  Contact Support
                </a>
              </>
            )}
          </div>
        )}
      </div>

      {job.status === 'queued' && (
        <>
          <p className="cc-async-job__msg">Your job is queued. Estimated start: ~15s</p>
          <ProgressTrack job={job} variant="muted" />
          <p className="cc-async-job__countdown cc-async-job__countdown--muted">{statusLine || 'Waiting in queue…'}</p>
        </>
      )}

      {job.status === 'running' && (
        <>
          <ProgressTrack job={job} variant="brand" />
          <p className="cc-async-job__countdown">
            {typeof remaining === 'number' ? `${Math.max(0, Math.ceil(remaining))}s remaining` : '—'}
            {statusLine ? ` · ${statusLine}` : ''}
          </p>
        </>
      )}

      {job.status === 'complete' && (
        <>
          <ProgressTrack job={job} variant="success" />
          <p className="cc-async-job__msg">{statusLine || 'Optimization complete. Review your recommendations.'}</p>
          {showView && (
            <div className="cc-async-job__footer">
              <button type="button" className="cc-async-job__btn cc-async-job__btn--primary" onClick={onView}>
                View Results
              </button>
            </div>
          )}
        </>
      )}

      {job.status === 'timeout' && (
        <>
          <ProgressTrack job={job} variant="warn" />
          <p className="cc-async-job__msg">This analysis took longer than expected. Retry or contact support.</p>
        </>
      )}

      {job.status === 'error' && (
        <>
          <ProgressTrack job={job} variant="error" />
          <p className="cc-async-job__msg">{job.errorMessage ?? 'Analysis failed. Retry or contact support.'}</p>
          <p className="cc-async-job__support">
            Support ID:{' '}
            <button type="button" className="cc-async-job__id-btn" onClick={onCopyId} title="Copy to clipboard">
              {job.correlationId ?? job.jobId}
            </button>
          </p>
        </>
      )}

      <p className="cc-async-job__time">
        {job.status === 'complete' || job.status === 'timeout' || job.status === 'error'
          ? formatCompleted(job)
          : formatStarted(job)}
      </p>
    </div>
  );
}

export default function AsyncJobTray({ jobs }: { jobs: AsyncJob[] }) {
  const { running, completed } = useMemo(() => {
    const r = jobs.filter((j) => j.status === 'queued' || j.status === 'running');
    const c = jobs.filter((j) => j.status === 'complete' || j.status === 'timeout' || j.status === 'error');
    const byRecent = (a: AsyncJob, b: AsyncJob) =>
      (b.startedAtMs ?? b.completedAtMs ?? 0) - (a.startedAtMs ?? a.completedAtMs ?? 0);
    r.sort(byRecent);
    c.sort((a, b) => (b.completedAtMs ?? b.startedAtMs ?? 0) - (a.completedAtMs ?? a.startedAtMs ?? 0));
    return { running: r, completed: c };
  }, [jobs]);

  return (
    <aside className="cc-async-tray" aria-labelledby="cc-async-tray-heading">
      <div className="cc-async-tray__chrome">
        <h2 id="cc-async-tray-heading" className="cc-async-tray__title">
          Async Job Tray
        </h2>
        <p className="cc-async-tray__subtitle">Background work — review when ready.</p>
      </div>

      <div className="cc-async-tray__body">
        <section className="cc-async-tray__section" aria-label="Running jobs">
          <h3 className="cc-async-tray__section-title">
            Running Jobs ({running.length})
          </h3>
          {running.length === 0 ? (
            <p className="cc-async-tray__empty">No jobs running.</p>
          ) : (
            <div className="cc-async-tray__list">
              {running.map((job) => (
                <AsyncJobCard key={job.jobId} job={job} />
              ))}
            </div>
          )}
        </section>

        {completed.length > 0 && (
          <section className="cc-async-tray__section cc-async-tray__section--completed" aria-label="Completed jobs">
            <h3 className="cc-async-tray__section-title">Completed ({completed.length})</h3>
            <div className="cc-async-tray__list">
              {completed.map((job) => (
                <AsyncJobCard key={job.jobId} job={job} />
              ))}
            </div>
          </section>
        )}
      </div>
    </aside>
  );
}
