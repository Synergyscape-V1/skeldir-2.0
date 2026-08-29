import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { COMMAND_CENTER_COPY } from './copy';
import { buildTriageHref } from './triageHref';
import {
  getNextUnresolvedTriageIssue,
  getTriageQueueSnapshot,
  getUnresolvedTriageIssues,
  markTriageIssueResolved,
} from './triageQueueStore';
import type { PriorityIssue } from './types';
import {
  PostActionSuccessOverlay,
  type PostActionOverlayMode,
} from '../components/triage/PostActionSuccessOverlay/PostActionSuccessOverlay';

const ADVANCE_DELAY_MS = 1500;

export interface UseTriageAdvanceOptions {
  enabled: boolean;
  issueId: string;
  issueTitle: string;
  successSignal: boolean;
}

export function useTriageAdvance({
  enabled,
  issueId,
  issueTitle,
  successSignal,
}: UseTriageAdvanceOptions) {
  const navigate = useNavigate();
  const [overlayOpen, setOverlayOpen] = useState(false);
  const [overlayMode, setOverlayMode] = useState<PostActionOverlayMode>('advance');
  const handledRef = useRef(false);

  useEffect(() => {
    handledRef.current = false;
  }, [issueId]);

  useEffect(() => {
    if (!enabled || !successSignal || handledRef.current) return;
    handledRef.current = true;

    const snapshot = getTriageQueueSnapshot();
    const remainingBefore = getUnresolvedTriageIssues(snapshot).filter((issue) => issue.id !== issueId).length;
    markTriageIssueResolved(
      issueId,
      COMMAND_CENTER_COPY.triage.advanceToast(issueTitle, remainingBefore),
    );

    const next = getNextUnresolvedTriageIssue(issueId);
    if (!next) {
      setOverlayMode('cleared');
      setOverlayOpen(true);
      return;
    }

    setOverlayMode('advance');
    setOverlayOpen(true);
    const timer = window.setTimeout(() => {
      const updated = getTriageQueueSnapshot();
      const rank = updated.issues.findIndex((issue) => issue.id === next.id) + 1;
      const href = buildTriageHref(next.actionHref, next.id, rank || 1, updated.issues.length);
      navigate(href);
    }, ADVANCE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [enabled, successSignal, issueId, issueTitle, navigate]);

  const overlay = (
    <PostActionSuccessOverlay
      open={overlayOpen}
      mode={overlayMode}
      onReturnToDashboard={() => setOverlayOpen(false)}
    />
  );

  return { overlay, overlayOpen, overlayMode };
}

export function resolveIssueTitle(
  issueId: string,
  fallback: string,
  issues: PriorityIssue[] = getTriageQueueSnapshot().issues,
): string {
  return issues.find((issue) => issue.id === issueId)?.title ?? fallback;
}
