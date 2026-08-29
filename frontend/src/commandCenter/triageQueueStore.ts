import type { PriorityIssue } from './types';

export type TriageQueueListener = () => void;

export interface TriageQueueSnapshot {
  issues: PriorityIssue[];
  resolvedIds: readonly string[];
  lastResolvedId: string | null;
  lastToast: string | null;
  sessionActive: boolean;
}

let issues: PriorityIssue[] = [];
let resolvedIds = new Set<string>();
let lastResolvedId: string | null = null;
let lastToast: string | null = null;
let sessionActive = false;
let cachedSnapshot: TriageQueueSnapshot = {
  issues: [],
  resolvedIds: [],
  lastResolvedId: null,
  lastToast: null,
  sessionActive: false,
};
const listeners = new Set<TriageQueueListener>();

function rebuildSnapshot(): TriageQueueSnapshot {
  cachedSnapshot = {
    issues: [...issues],
    resolvedIds: [...resolvedIds],
    lastResolvedId,
    lastToast,
    sessionActive,
  };
  return cachedSnapshot;
}

function emit(): void {
  rebuildSnapshot();
  for (const listener of listeners) listener();
}

function issueIdsKey(list: PriorityIssue[]): string {
  return list.map((issue) => issue.id).join('|');
}

function sameIssueSet(a: PriorityIssue[], b: PriorityIssue[]): boolean {
  if (a.length !== b.length) return false;
  return issueIdsKey(a) === issueIdsKey(b);
}

export function subscribeTriageQueue(listener: TriageQueueListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getTriageQueueSnapshot(): TriageQueueSnapshot {
  return cachedSnapshot;
}

export function beginTriageSession(nextIssues: PriorityIssue[]): void {
  const next = nextIssues.map((issue) => ({ ...issue }));
  const liveIds = new Set(next.map((issue) => issue.id));
  const nextResolved = new Set([...resolvedIds].filter((id) => liveIds.has(id)));
  const resolvedChanged =
    nextResolved.size !== resolvedIds.size || [...nextResolved].some((id) => !resolvedIds.has(id));
  const issuesChanged = !sameIssueSet(issues, next);
  const wasInactive = !sessionActive;

  if (!issuesChanged && !resolvedChanged && !wasInactive && lastToast === null) {
    if (!sessionActive && next.length > 0) {
      sessionActive = true;
      emit();
    }
    return;
  }

  issues = next;
  resolvedIds = nextResolved;
  sessionActive = next.length > 0;
  lastToast = null;
  emit();
}

export function syncTriageIssues(nextIssues: PriorityIssue[]): void {
  if (!sessionActive && nextIssues.length === 0) {
    if (issues.length === 0) return;
    issues = [];
    emit();
    return;
  }
  if (!sessionActive) {
    beginTriageSession(nextIssues);
    return;
  }

  const byId = new Map(nextIssues.map((issue) => [issue.id, issue]));
  const merged: PriorityIssue[] = [];
  for (const issue of issues) {
    const live = byId.get(issue.id);
    if (live) merged.push({ ...live });
  }
  for (const issue of nextIssues) {
    if (!merged.some((row) => row.id === issue.id)) {
      merged.push({ ...issue });
    }
  }

  const liveIds = new Set(merged.map((issue) => issue.id));
  const nextResolved = new Set([...resolvedIds].filter((id) => liveIds.has(id)));
  const resolvedChanged =
    nextResolved.size !== resolvedIds.size || [...nextResolved].some((id) => !resolvedIds.has(id));

  if (sameIssueSet(issues, merged) && !resolvedChanged) {
    return;
  }

  issues = merged;
  resolvedIds = nextResolved;
  emit();
}

export function markTriageIssueResolved(issueId: string, toast?: string): void {
  if (!issues.some((issue) => issue.id === issueId)) return;
  if (resolvedIds.has(issueId) && (toast ?? null) === lastToast) return;
  resolvedIds.add(issueId);
  lastResolvedId = issueId;
  lastToast = toast ?? null;
  emit();
}

export function clearTriageToast(): void {
  if (lastToast === null) return;
  lastToast = null;
  emit();
}

export function resetTriageQueueSession(): void {
  if (
    issues.length === 0 &&
    resolvedIds.size === 0 &&
    lastResolvedId === null &&
    lastToast === null &&
    !sessionActive
  ) {
    return;
  }
  issues = [];
  resolvedIds = new Set();
  lastResolvedId = null;
  lastToast = null;
  sessionActive = false;
  emit();
}

export function getUnresolvedTriageIssues(
  snapshot: TriageQueueSnapshot = getTriageQueueSnapshot(),
): PriorityIssue[] {
  const resolved = new Set(snapshot.resolvedIds);
  return snapshot.issues.filter((issue) => !resolved.has(issue.id));
}

export function getNextUnresolvedTriageIssue(
  afterIssueId?: string | null,
  snapshot: TriageQueueSnapshot = getTriageQueueSnapshot(),
): PriorityIssue | null {
  const unresolved = getUnresolvedTriageIssues(snapshot);
  if (unresolved.length === 0) return null;
  if (!afterIssueId) return unresolved[0] ?? null;
  const afterIndex = snapshot.issues.findIndex((issue) => issue.id === afterIssueId);
  if (afterIndex < 0) return unresolved[0] ?? null;
  for (let i = afterIndex + 1; i < snapshot.issues.length; i++) {
    const candidate = snapshot.issues[i]!;
    if (!snapshot.resolvedIds.includes(candidate.id)) return candidate;
  }
  return unresolved[0] ?? null;
}

export function countBlockingIssues(
  aggregateIssues: PriorityIssue[],
  snapshot: TriageQueueSnapshot = getTriageQueueSnapshot(),
): number {
  if (snapshot.sessionActive && snapshot.issues.length > 0) {
    return getUnresolvedTriageIssues(snapshot).length;
  }
  return aggregateIssues.length;
}

export function isTriageIssueResolved(
  issueId: string,
  snapshot: TriageQueueSnapshot = getTriageQueueSnapshot(),
): boolean {
  return snapshot.resolvedIds.includes(issueId);
}
