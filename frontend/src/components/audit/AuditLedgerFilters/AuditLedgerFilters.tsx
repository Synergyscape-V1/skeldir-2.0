import { useEffect, useState, type FormEvent } from 'react';
import type { AuditLogMode, ForensicActionCategory } from '../../../operationalAudit/types';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import {
  FORENSIC_ACTION_CATEGORIES,
  FORENSIC_ACTION_CATEGORY_LABELS,
  FORENSIC_ACTOR_SUGGESTIONS,
} from '../../../operationalAudit/forensicBusinessTriage';
import type { AuditFilters } from '../../../operationalAudit/parseAuditFilters';
import {
  auditFilterCriteriaEqual,
  hasActiveAuditFilters,
} from '../../../operationalAudit/auditFilterConfig';
import primaryAction from '../../../styles/primaryAction.module.css';
import shared from '../../../styles/shared.module.css';
import styles from './AuditLedgerFilters.module.css';

export interface AuditLedgerFiltersProps {
  logMode: AuditLogMode;
  filters: AuditFilters;
  onApply: (filters: AuditFilters) => void;
  onClear: () => void;
}

const HTTP_STATUS_CODES: Array<number | 'all'> = ['all', 200, 403, 404, 500, 503];
const FORENSIC_ACTION_OPTIONS: Array<ForensicActionCategory | 'all'> = [
  'all',
  ...FORENSIC_ACTION_CATEGORIES,
];

function selectedForensicActionCategory(
  categories: ForensicActionCategory[] | undefined,
): ForensicActionCategory | 'all' {
  if (!categories || categories.length !== 1) return 'all';
  return categories[0] ?? 'all';
}

export function AuditLedgerFilters({ logMode, filters, onApply, onClear }: AuditLedgerFiltersProps) {
  const [draft, setDraft] = useState<AuditFilters>({ ...filters, logMode });

  useEffect(() => {
    setDraft({ ...filters, logMode });
  }, [filters, logMode]);

  const update = (patch: Partial<AuditFilters>) =>
    setDraft((current) => ({ ...current, ...patch, logMode }));

  const isDirty = !auditFilterCriteriaEqual(draft, { ...filters, logMode });
  const canClear = hasActiveAuditFilters(draft) || hasActiveAuditFilters(filters);

  const handleApply = () => {
    if (!isDirty) return;
    onApply({ ...draft, logMode });
  };

  const handleClear = () => {
    onClear();
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    handleApply();
  };

  return (
    <fieldset className={styles.filters} data-audit-ledger-filters data-audit-log-mode={logMode}>
      <legend className={styles.legend}>
        {logMode === 'forensic_log'
          ? OPERATIONAL_AUDIT_COPY.forensicFiltersLabel
          : OPERATIONAL_AUDIT_COPY.auditFiltersLabel}
      </legend>
      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.rows}>
          {logMode === 'forensic_log' ? (
            <>
              <div className={styles.primaryRow}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>{OPERATIONAL_AUDIT_COPY.filterWhoDidIt}</span>
                  <input
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.actor ?? ''}
                    onChange={(e) => update({ actor: e.target.value || undefined })}
                    placeholder={OPERATIONAL_AUDIT_COPY.filterWhoPlaceholder}
                    list="forensic-actor-suggestions"
                    autoComplete="off"
                  />
                  <datalist id="forensic-actor-suggestions">
                    {FORENSIC_ACTOR_SUGGESTIONS.map((name) => (
                      <option key={name} value={name} />
                    ))}
                  </datalist>
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>{OPERATIONAL_AUDIT_COPY.filterOrderClaim}</span>
                  <input
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.claimId ?? ''}
                    onChange={(e) => update({ claimId: e.target.value || undefined })}
                    placeholder={OPERATIONAL_AUDIT_COPY.filterOrderClaimPlaceholder}
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>{OPERATIONAL_AUDIT_COPY.filterEnvelope}</span>
                  <input
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.envelopeId ?? ''}
                    onChange={(e) => update({ envelopeId: e.target.value || undefined })}
                    placeholder={OPERATIONAL_AUDIT_COPY.filterEnvelopePlaceholder}
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>{OPERATIONAL_AUDIT_COPY.filterWhatTheyDid}</span>
                  <select
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={selectedForensicActionCategory(draft.actionCategories)}
                    onChange={(e) => {
                      const value = e.target.value as ForensicActionCategory | 'all';
                      update({
                        actionCategories: value === 'all' ? undefined : [value],
                      });
                    }}
                  >
                    {FORENSIC_ACTION_OPTIONS.map((value) => (
                      <option key={value} value={value}>
                        {value === 'all'
                          ? OPERATIONAL_AUDIT_COPY.filterWhatTheyDidAll
                          : FORENSIC_ACTION_CATEGORY_LABELS[value]}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className={styles.secondaryRow}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Date from</span>
                  <input
                    type="date"
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.dateFrom?.slice(0, 10) ?? ''}
                    onChange={(e) =>
                      update({
                        dateFrom: e.target.value ? `${e.target.value}T00:00:00.000Z` : undefined,
                      })
                    }
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Date to</span>
                  <input
                    type="date"
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.dateTo?.slice(0, 10) ?? ''}
                    onChange={(e) =>
                      update({
                        dateTo: e.target.value ? `${e.target.value}T23:59:59.999Z` : undefined,
                      })
                    }
                  />
                </label>
              </div>
            </>
          ) : (
            <>
              <div className={styles.primaryRow}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Actor</span>
                  <input
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.actor ?? ''}
                    onChange={(e) => update({ actor: e.target.value || undefined })}
                    placeholder="actor_01"
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Target envelope id</span>
                  <input
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.envelopeId ?? ''}
                    onChange={(e) => update({ envelopeId: e.target.value || undefined })}
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Endpoint URL</span>
                  <input
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.endpoint ?? ''}
                    onChange={(e) => update({ endpoint: e.target.value || undefined })}
                    placeholder="/v1/trust/envelopes"
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>HTTP status</span>
                  <select
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.httpStatusCode ?? 'all'}
                    onChange={(e) => {
                      const value = e.target.value;
                      update({
                        httpStatusCode: value === 'all' ? undefined : Number.parseInt(value, 10),
                      });
                    }}
                  >
                    {HTTP_STATUS_CODES.map((value) => (
                      <option key={String(value)} value={value}>
                        {value === 'all' ? 'All statuses' : String(value)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className={styles.secondaryRow}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Date from</span>
                  <input
                    type="date"
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.dateFrom?.slice(0, 10) ?? ''}
                    onChange={(e) =>
                      update({
                        dateFrom: e.target.value ? `${e.target.value}T00:00:00.000Z` : undefined,
                      })
                    }
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Date to</span>
                  <input
                    type="date"
                    className={[styles.control, shared.focusVisible].join(' ')}
                    value={draft.dateTo?.slice(0, 10) ?? ''}
                    onChange={(e) =>
                      update({
                        dateTo: e.target.value ? `${e.target.value}T23:59:59.999Z` : undefined,
                      })
                    }
                  />
                </label>
              </div>
            </>
          )}
        </div>
        <div className={styles.actionsRow}>
          <button
            type="submit"
            className={[primaryAction.primaryAction, shared.focusVisible].join(' ')}
            disabled={!isDirty}
          >
            {OPERATIONAL_AUDIT_COPY.auditApplyFilters}
          </button>
          <button
            type="button"
            className={[styles.clearButton, shared.focusVisible].join(' ')}
            disabled={!canClear}
            onClick={handleClear}
          >
            {OPERATIONAL_AUDIT_COPY.auditClearFilters}
          </button>
        </div>
      </form>
    </fieldset>
  );
}
