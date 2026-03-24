import React, { forwardRef, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, AlertTriangle, Check, Loader2 } from 'lucide-react';
import CredibleIntervalBar from './CredibleIntervalBar';
import type { ActionDirective, DirectiveConfidenceRange } from '../types/actionDirective';
import { MAX_ACTION_DIRECTIVES, sortDirectives } from '../types/actionDirective';

function defaultImplication(bucket: DirectiveConfidenceRange['bucket']): string {
  switch (bucket) {
    case 'narrow':
      return 'Safe to act on this data';
    case 'medium':
      return 'Monitor for 1–2 more weeks';
    case 'wide':
      return 'Gather more data before acting';
    default:
      return '';
  }
}

function BucketIcon({ bucket }: { bucket: DirectiveConfidenceRange['bucket'] }) {
  const common = { size: 11 as const, strokeWidth: 2 as const, 'aria-hidden': true as const };
  if (bucket === 'narrow') return <Check {...common} className="cc-directive-card__bucket-icon cc-directive-card__bucket-icon--narrow" />;
  if (bucket === 'medium') return <AlertCircle {...common} className="cc-directive-card__bucket-icon cc-directive-card__bucket-icon--medium" />;
  return <AlertTriangle {...common} className="cc-directive-card__bucket-icon cc-directive-card__bucket-icon--wide" />;
}

function DirectiveCard({
  directive,
  onDismiss,
}: {
  directive: ActionDirective;
  onDismiss: (id: string) => void;
}) {
  const navigate = useNavigate();

  const go = (route?: string) => {
    if (route) navigate(route);
  };

  const isCollapsed = directive.status === 'completed' || directive.status === 'approved';
  const isRejected = directive.status === 'rejected';
  const isExecuting = directive.status === 'executing';
  const isCompact = !directive.confidenceRange && directive.drivers.length === 0;

  if (isCollapsed) {
    return (
      <div
        role="listitem"
        className={`cc-directive-card cc-directive-card--collapsed ${directive.status === 'approved' ? 'cc-directive-card--approved-bg' : ''}`}
      >
        <span className="cc-directive-card__collapsed-check" aria-hidden>
          <Check size={14} strokeWidth={2} />
        </span>
        <span className="cc-directive-card__collapsed-headline">{directive.headline}</span>
        <button type="button" className="cc-directive-card__link" onClick={() => go(directive.primaryAction.route)}>
          View
        </button>
      </div>
    );
  }

  if (isRejected) {
    return (
      <div role="listitem" className="cc-directive-card cc-directive-card--rejected">
        <div className="cc-directive-card__row">
          <span className="cc-directive-card__priority cc-directive-card__priority--routine">◉ Priority {directive.priority}</span>
          <span className="cc-directive-card__time">{directive.relativeTime}</span>
        </div>
        <p className="cc-directive-card__headline cc-directive-card__headline--rejected">{directive.headline}</p>
        <span className="cc-directive-card__badge-rejected">Rejected</span>
      </div>
    );
  }

  const priorityUrgent = directive.priority <= 2;
  const isPending = directive.status === 'pending';

  const hasOutcome = Boolean(directive.projectedOutcomeText);
  const hasDrivers = directive.drivers.length > 0;
  const hasConfidence = Boolean(directive.confidenceRange);
  const showDirectiveBody = !isCompact && (hasOutcome || hasDrivers || hasConfidence);

  return (
    <article
      role="listitem"
      className={`cc-directive-card cc-directive-card--elevate ${isExecuting ? 'cc-directive-card--executing' : ''} ${isPending ? 'cc-directive-card--pending' : ''}`}
    >
      <div className="cc-directive-card__row">
        <span
          className={`cc-directive-card__priority ${priorityUrgent ? 'cc-directive-card__priority--urgent' : 'cc-directive-card__priority--routine'} ${isPending ? 'cc-directive-card__priority--pulse' : ''}`}
        >
          ◉ Priority {directive.priority}
        </span>
        <span className="cc-directive-card__time">{directive.relativeTime}</span>
      </div>

      {isExecuting && (
        <div className="cc-directive-card__executing">
          <Loader2 size={15} className="cc-directive-card__spinner" aria-hidden />
          <span>Applying changes…</span>
        </div>
      )}

      <h3 className="cc-directive-card__headline">{directive.headline}</h3>

      {showDirectiveBody ? (
        <div className="cc-directive-card__body-grid">
          {hasOutcome || hasDrivers ? (
            <div className="cc-directive-card__body-main">
              {hasOutcome ? <p className="cc-directive-card__outcome">{directive.projectedOutcomeText}</p> : null}
              {hasDrivers ? (
                <div className="cc-directive-card__why">
                  <p className="cc-directive-card__why-label">Why:</p>
                  <ul className="cc-directive-card__drivers">
                    {directive.drivers.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
          {hasConfidence && directive.confidenceRange ? (
            <div className="cc-directive-card__body-aside" title="Open explanation drawer for detailed reasoning (coming soon)">
              <div className="cc-directive-card__confidence">
                <div className="cc-directive-card__confidence-frame">
                  <div className="cc-directive-card__confidence-header">
                    <div className="cc-directive-card__confidence-top">
                      <span className="cc-directive-card__confidence-title">Likely range</span>
                      <span className="cc-directive-card__confidence-implication">
                        <BucketIcon bucket={directive.confidenceRange.bucket} />
                        <span>
                          {directive.confidenceRange.actionImplication ?? defaultImplication(directive.confidenceRange.bucket)}
                        </span>
                      </span>
                    </div>
                    <p className="cc-directive-card__confidence-range-text">
                      {directive.confidenceRange.bucket === 'narrow'
                        ? 'Narrow'
                        : directive.confidenceRange.bucket === 'medium'
                          ? 'Medium'
                          : 'Wide'}{' '}
                      range: {directive.confidenceRange.lowerLabel} – {directive.confidenceRange.upperLabel}
                    </p>
                  </div>
                  <div className="cc-directive-card__confidence-bar-wrap">
                    <CredibleIntervalBar
                      lower={directive.confidenceRange.lower}
                      upper={directive.confidenceRange.upper}
                      estimate={directive.confidenceRange.estimate}
                      bucket={directive.confidenceRange.bucket}
                      height={4}
                      widthPercent={100}
                      variant="directive"
                    />
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {!isExecuting && (
        <div className="cc-directive-card__actions">
          <button
            type="button"
            className="cc-directive-card__btn cc-directive-card__btn--primary"
            onClick={() => go(directive.primaryAction.route)}
          >
            {directive.primaryAction.label}
          </button>
          {!isCompact && directive.secondaryAction?.type === 'dismiss' && (
            <button type="button" className="cc-directive-card__btn cc-directive-card__btn--ghost" onClick={() => onDismiss(directive.id)}>
              {directive.secondaryAction.label}
            </button>
          )}
        </div>
      )}
    </article>
  );
}

const ActionDirectivesPanel = forwardRef<HTMLDivElement, { directives: ActionDirective[] }>(function ActionDirectivesPanel(
  { directives },
  ref
) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const visible = useMemo(() => {
    const sorted = sortDirectives(directives.filter((d) => !dismissed.has(d.id)));
    return sorted.slice(0, MAX_ACTION_DIRECTIVES);
  }, [directives, dismissed]);

  const activePending = useMemo(
    () => visible.filter((d) => d.status === 'pending' || d.status === 'executing').length,
    [visible]
  );

  return (
    <section className="cc-directives-panel" aria-labelledby="cc-directives-heading">
      <div ref={ref} className="cc-directives-panel__shell">
        <div className="cc-directives-panel__header">
          <h2 id="cc-directives-heading" className="cc-directives-panel__title">
            Action Directives
          </h2>
          <div className="cc-directives-panel__header-right">
            <span className="cc-directives-panel__badge">{activePending} active</span>
            <button type="button" className="cc-directives-panel__view-all">
              View all
            </button>
          </div>
        </div>

        <div className="cc-directives-panel__stack" role="list">
          {visible.map((d) => (
            <DirectiveCard key={d.id} directive={d} onDismiss={(id) => setDismissed((prev) => new Set([...prev, id]))} />
          ))}
        </div>
      </div>
    </section>
  );
});

export default ActionDirectivesPanel;
