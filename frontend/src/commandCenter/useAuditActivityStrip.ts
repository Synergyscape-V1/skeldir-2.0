import { useCallback, useEffect, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { fetchAuditActivityStrip } from './commandCenterAuditActivity';
import { AUDIT_ACTIVITY_POLL_INTERVAL_MS } from './auditActivityPolicy';
import type { AuditActivityRow } from './types';

export function useAuditActivityStrip(initialRows: AuditActivityRow[]): AuditActivityRow[] {
  const [rows, setRows] = useState(initialRows);

  useEffect(() => {
    setRows(initialRows);
  }, [initialRows]);

  const poll = useCallback(async (signal: AbortSignal) => {
    const { tenant } = getAuthState();
    if (!tenant) return;
    try {
      const next = await fetchAuditActivityStrip(tenant.tenantId, signal);
      if (!signal.aborted) {
        setRows(next);
      }
    } catch {
      /* Retain last known vault log on poll failure. */
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const interval = window.setInterval(() => {
      void poll(controller.signal);
    }, AUDIT_ACTIVITY_POLL_INTERVAL_MS);

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [poll]);

  return rows;
}
