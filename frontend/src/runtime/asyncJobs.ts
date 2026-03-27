export type AsyncJobStatus = "queued" | "running" | "complete" | "timeout" | "error";

export type AsyncJobType =
  | "budget_optimization"
  | "data_backfill"
  | "attribution_refresh"
  | "sync";

export interface AsyncJob {
  jobId: string;
  type: AsyncJobType;
  label: string;
  status: AsyncJobStatus;
  statusMessage?: string;
  correlationId?: string;
  startedAtMs?: number;
  completedAtMs?: number;
  durationSeconds?: number;
  maxDurationSeconds?: number;
  elapsedSeconds?: number;
  timeRemainingSeconds?: number;
  payload?: Record<string, unknown>;
  errorMessage?: string;
}

type AsyncJobSubscriber = (jobs: AsyncJob[]) => void;

const jobs = new Map<string, AsyncJob>();
const subscribers = new Set<AsyncJobSubscriber>();

let runtimeBootstrapped = false;
let runtimeTimer: number | null = null;

function nextUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function cloneAndSortJobs(): AsyncJob[] {
  return [...jobs.values()].sort((a, b) => {
    const left = a.startedAtMs ?? a.completedAtMs ?? 0;
    const right = b.startedAtMs ?? b.completedAtMs ?? 0;
    return right - left;
  });
}

function notifySubscribers(): void {
  const snapshot = cloneAndSortJobs();
  subscribers.forEach((subscriber) => subscriber(snapshot));
}

function updateJob(jobId: string, patch: Partial<AsyncJob>): void {
  const current = jobs.get(jobId);
  if (!current) {
    return;
  }
  jobs.set(jobId, { ...current, ...patch });
}

function advanceRuntime(): void {
  const now = Date.now();
  let changed = false;

  for (const [jobId, job] of jobs.entries()) {
    if (job.status === "queued") {
      const startedAtMs = now;
      const durationSeconds = job.durationSeconds ?? job.maxDurationSeconds ?? 45;
      updateJob(jobId, {
        status: "running",
        startedAtMs,
        elapsedSeconds: 0,
        timeRemainingSeconds: durationSeconds,
        maxDurationSeconds: durationSeconds,
        statusMessage: job.statusMessage ?? "Job started",
      });
      changed = true;
      continue;
    }

    if (job.status !== "running") {
      continue;
    }

    const startedAt = job.startedAtMs ?? now;
    const durationSeconds = job.durationSeconds ?? job.maxDurationSeconds ?? 45;
    const elapsedSeconds = Math.max(0, Math.floor((now - startedAt) / 1000));
    const timeRemainingSeconds = Math.max(0, durationSeconds - elapsedSeconds);

    if (timeRemainingSeconds <= 0) {
      updateJob(jobId, {
        status: "complete",
        elapsedSeconds: durationSeconds,
        timeRemainingSeconds: 0,
        completedAtMs: now,
        statusMessage: "Completed",
      });
      changed = true;
      continue;
    }

    if (
      job.elapsedSeconds !== elapsedSeconds ||
      job.timeRemainingSeconds !== timeRemainingSeconds
    ) {
      updateJob(jobId, {
        elapsedSeconds,
        timeRemainingSeconds,
        statusMessage: "Running",
      });
      changed = true;
    }
  }

  if (changed) {
    notifySubscribers();
  }
}

function ensureRuntimeTimer(): void {
  if (runtimeTimer !== null || typeof window === "undefined") {
    return;
  }
  runtimeTimer = window.setInterval(advanceRuntime, 1000);
}

export function bootstrapAsyncJobRuntime(): void {
  if (runtimeBootstrapped) {
    ensureRuntimeTimer();
    return;
  }
  runtimeBootstrapped = true;
  ensureRuntimeTimer();
}

export function getAsyncJobs(): AsyncJob[] {
  return cloneAndSortJobs();
}

export function subscribeAsyncJobs(subscriber: AsyncJobSubscriber): () => void {
  subscribers.add(subscriber);
  subscriber(getAsyncJobs());
  return () => {
    subscribers.delete(subscriber);
  };
}

export function ensureSeedJobs(seedJobs: AsyncJob[]): void {
  let changed = false;
  for (const seed of seedJobs) {
    if (!jobs.has(seed.jobId)) {
      jobs.set(seed.jobId, { ...seed });
      changed = true;
    }
  }
  if (changed) {
    notifySubscribers();
  }
}

export function startBudgetOptimizationJob(payload?: Record<string, unknown>): string {
  const jobId = nextUuid();
  const now = Date.now();
  const durationSeconds =
    typeof payload?.durationSeconds === "number" && Number.isFinite(payload.durationSeconds)
      ? Math.max(5, Math.floor(payload.durationSeconds))
      : 45;
  jobs.set(jobId, {
    jobId,
    type: "budget_optimization",
    label: "Budget optimization",
    status: "queued",
    startedAtMs: now,
    durationSeconds,
    maxDurationSeconds: durationSeconds,
    elapsedSeconds: 0,
    timeRemainingSeconds: durationSeconds,
    payload,
    correlationId: nextUuid(),
    statusMessage: "Queued",
  });
  notifySubscribers();
  return jobId;
}

export function cancelAsyncJob(jobId: string): void {
  const existing = jobs.get(jobId);
  if (!existing) {
    return;
  }
  jobs.set(jobId, {
    ...existing,
    status: "timeout",
    completedAtMs: Date.now(),
    statusMessage: "Cancelled by reviewer",
    errorMessage: "Cancelled",
  });
  notifySubscribers();
}

export function retryAsyncJob(jobId: string): void {
  const existing = jobs.get(jobId);
  if (!existing) {
    return;
  }
  const durationSeconds = existing.durationSeconds ?? existing.maxDurationSeconds ?? 45;
  jobs.set(jobId, {
    ...existing,
    status: "queued",
    startedAtMs: Date.now(),
    completedAtMs: undefined,
    elapsedSeconds: 0,
    timeRemainingSeconds: durationSeconds,
    durationSeconds,
    maxDurationSeconds: durationSeconds,
    statusMessage: "Retry queued",
    errorMessage: undefined,
  });
  notifySubscribers();
}
