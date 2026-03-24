import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { RevenueDiscrepancyAlertModel, RevenueDiscrepancySeverity } from '../types/revenueDiscrepancy';

function inferSeverity(pct: number): RevenueDiscrepancySeverity {
  return Math.abs(pct) > 25 ? 'critical' : 'caution';
}

const TOOLTIP =
  'Discrepancy is calculated as (verified revenue − platform-claimed revenue) ÷ platform-claimed revenue × 100%.';

export default function RevenueDiscrepancyBanner({
  data,
  verificationHref = '/data',
}: {
  data: RevenueDiscrepancyAlertModel;
  /** Where “View Revenue Verification” navigates (Data Health / revenue matching). */
  verificationHref?: string;
}) {
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(false);

  const severity = data.severity ?? inferSeverity(data.discrepancyPct);
  const pctLabel = `${data.discrepancyPct.toFixed(1)}%`;

  const otherNote = useMemo(() => {
    const n = data.otherPlatformsCount;
    if (typeof n !== 'number' || n <= 0) return null;
    return `+${n} other platform${n === 1 ? '' : 's'} ${n === 1 ? 'has' : 'have'} discrepancies.`;
  }, [data.otherPlatformsCount]);

  if (!data.visible || dismissed) return null;

  const critical = severity === 'critical';

  return (
    <div
      className={`cc-rev-disc-banner cc-rev-disc-banner--${critical ? 'critical' : 'caution'}`}
      role="region"
      aria-label="Revenue discrepancy alert"
    >
      <div className="cc-rev-disc-banner__top">
        <div className="cc-rev-disc-banner__body">
          <p className="cc-rev-disc-banner__text">
            {data.primaryPlatformName} reported <span className="cc-rev-disc-banner__amount">{data.claimedRevenueFormatted}</span> in
            revenue. Verified revenue from {data.verifiedSource}:{' '}
            <span className="cc-rev-disc-banner__amount">{data.verifiedRevenueFormatted}</span>.{' '}
            <strong className="cc-rev-disc-banner__disc" title={TOOLTIP}>
              Discrepancy: {pctLabel}
            </strong>
            .{' '}
            {critical && <span className="cc-rev-disc-banner__severe">Severe discrepancy — review urgently.</span>}
          </p>
          <div
            className={`cc-rev-disc-banner__subrow${otherNote ? '' : ' cc-rev-disc-banner__subrow--link-only'}`}
          >
            {otherNote ? <p className="cc-rev-disc-banner__meta">{otherNote}</p> : null}
            <button type="button" className="cc-rev-disc-banner__link" onClick={() => navigate(verificationHref)}>
              View Revenue Verification →
            </button>
          </div>
        </div>
        <button
          type="button"
          className="cc-rev-disc-banner__dismiss"
          aria-label="Dismiss alert for this session"
          onClick={() => setDismissed(true)}
        >
          ×
        </button>
      </div>
    </div>
  );
}
