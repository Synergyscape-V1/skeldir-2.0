import { useEffect, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getDefaultOperationalAuditClient } from '../operationalAudit/operationalAuditClient';

export function useTrustIndexKillSwitch(): boolean {
  const [killSwitchActive, setKillSwitchActive] = useState(false);

  useEffect(() => {
    const { tenant } = getAuthState();
    if (!tenant) return;

    const controller = new AbortController();
    void getDefaultOperationalAuditClient()
      .getSystemHealth(tenant.tenantId, controller.signal)
      .then((outcome) => {
        if (controller.signal.aborted) return;
        setKillSwitchActive(outcome.kind === 'health_api_paused');
      })
      .catch(() => {
        if (!controller.signal.aborted) setKillSwitchActive(false);
      });

    return () => controller.abort();
  }, []);

  return killSwitchActive;
}
