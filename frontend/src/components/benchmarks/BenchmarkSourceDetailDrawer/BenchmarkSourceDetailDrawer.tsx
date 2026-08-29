import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { buildClaimTrustDrawerHref } from '../../../trustIndex/envelopeClaimRouting';
import { getAuthState } from '../../../auth/sessionStore';
import { getDefaultBenchmarkDetailClient } from '../../../benchmarks/benchmarkDetailClient';
import { BENCHMARKS_COPY } from '../../../benchmarks/copy';
import {
  actionabilityLabel,
  comparabilityLabel,
  coverageClassLabel,
  evidenceClassLabel,
  formatBenchmarkValue,
} from '../../../benchmarks/benchmarkDisplay';
import { resolveTableActionability } from '../../../benchmarks/benchmarkTableDisplay';
import type { BenchmarkRowDTO } from '../../../ledger/types';
import { Drawer } from '../../layout/Drawer/Drawer';
import {
  ActionabilityPill,
  ComparabilityIndicator,
  CoverageClassBadge,
  EvidenceClassBadge,
} from '../BenchmarkBadges/BenchmarkBadges';
import styles from './BenchmarkSourceDetailDrawer.module.css';

export interface BenchmarkSourceDetailDrawerProps {
  benchmarkId: string | null;
  open: boolean;
  onClose: () => void;
  triggerRef?: React.RefObject<HTMLElement | null>;
}

export function BenchmarkSourceDetailDrawer({
  benchmarkId,
  open,
  onClose,
  triggerRef,
}: BenchmarkSourceDetailDrawerProps) {
  const [detail, setDetail] = useState<BenchmarkRowDTO | null>(null);
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const activeRef = useRef(0);

  const load = useCallback(async () => {
    if (!benchmarkId || !open) return;
    const requestId = ++activeRef.current;
    setLoading(true);
    setError(undefined);
    const { tenant } = getAuthState();
    const outcome = await getDefaultBenchmarkDetailClient().getBenchmarkDetail(
      tenant?.tenantId ?? '',
      benchmarkId,
    );
    if (activeRef.current !== requestId) return;
    setLoading(false);
    if (outcome.kind === 'loaded' && outcome.detail) setDetail(outcome.detail);
    else setError(outcome.message ?? BENCHMARKS_COPY.drawer.error);
  }, [benchmarkId, open]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      triggerRef={triggerRef}
      title={detail?.benchmarkName ?? BENCHMARKS_COPY.drawer.title}
      state={loading ? 'loading' : error ? 'error' : 'open'}
      errorMessage={error}
      progressCopy={BENCHMARKS_COPY.drawer.loading}
      onRetry={load}
    >
      {detail ? (
        <div data-benchmark-source-detail-drawer className={styles.content}>
          <dl className={styles.fieldGrid}>
            <div>
              <dt>Benchmark name</dt>
              <dd>{detail.benchmarkName}</dd>
            </div>
            <div>
              <dt>Raw benchmark</dt>
              <dd>{formatBenchmarkValue(detail.rawBenchmark)}</dd>
            </div>
            <div>
              <dt>Decision-safe benchmark</dt>
              <dd>{formatBenchmarkValue(detail.decisionSafeBenchmark)}</dd>
            </div>
            <div>
              <dt>Evidence class</dt>
              <dd>
                <EvidenceClassBadge value={detail.evidenceClass} showHistoricalDisclaimer />
              </dd>
            </div>
            <div>
              <dt>Coverage class</dt>
              <dd>
                <CoverageClassBadge value={detail.coverageClass} />
              </dd>
            </div>
            <div>
              <dt>Suppression reason</dt>
              <dd>{detail.suppressionReason ?? detail.suppressionReasonCode ?? '—'}</dd>
            </div>
            <div>
              <dt>Comparable to previous</dt>
              <dd>
                <ComparabilityIndicator
                  value={detail.comparability}
                  sourceTransition={detail.sourceTransition}
                />
              </dd>
            </div>
            <div>
              <dt>Actionability</dt>
              <dd>
                <ActionabilityPill value={resolveTableActionability(detail)} />
              </dd>
            </div>
          </dl>

          {detail.sourceTransition ? (
            <p className={styles.transitionCopy} role="status">
              {BENCHMARKS_COPY.drawer.sourceTransitionCopy}
              {detail.transitionReason ? ` ${detail.transitionReason}` : ''}
            </p>
          ) : null}

          <div className={styles.links}>
            {detail.trustEnvelopeId ? (
              <Link to={buildClaimTrustDrawerHref(detail.trustEnvelopeId)} className={styles.link}>
                {BENCHMARKS_COPY.drawer.relatedTrustEnvelope}
              </Link>
            ) : null}
            {detail.auditReference ? (
              <Link to={`/app/audit?benchmark_id=${detail.benchmarkId}`} className={styles.link}>
                {BENCHMARKS_COPY.drawer.relatedAudit}
              </Link>
            ) : null}
          </div>

          <p className={styles.meta} aria-live="polite">
            Evidence: {evidenceClassLabel(detail.evidenceClass)} · Coverage:{' '}
            {coverageClassLabel(detail.coverageClass)} · Actionability:{' '}
            {actionabilityLabel(detail.actionability)} · Comparability:{' '}
            {comparabilityLabel(detail.comparability)}
          </p>
        </div>
      ) : null}
    </Drawer>
  );
}
