import { useEffect, useState } from 'react';
import { getAuthState } from '../../../auth/sessionStore';
import { getDefaultGovernanceClient } from '../../../governance/governanceClient';
import { formatRelativeUpdatedTime } from '../../../lib/relativeTime';
import { TRUST_ENVELOPE_INDEX_COPY } from '../../../trustIndex/copy';
import {
  formatExternalExportPolicyNotice,
  resolveExternalExportAuthority,
} from '../../../trustIndex/externalExportPolicyNotice';
import { Typography } from '../../layout/Typography/Typography';
import { TrustEnvelopeIndexPageHeaderActions } from './TrustEnvelopeIndexPageHeaderActions';
import styles from './TrustEnvelopeIndexPage.module.css';

export interface TrustEnvelopeIndexPageHeaderProps {
  lastUpdatedAt?: string;
  latestEnvelopeId?: string | null;
  loading?: boolean;
  readOnly?: boolean;
}

export function TrustEnvelopeIndexPageHeader({
  lastUpdatedAt,
  latestEnvelopeId,
  loading,
  readOnly = false,
}: TrustEnvelopeIndexPageHeaderProps) {
  const [policyNotice, setPolicyNotice] = useState<string>();

  useEffect(() => {
    const { tenant } = getAuthState();
    if (!tenant) return;

    const controller = new AbortController();
    void getDefaultGovernanceClient()
      .getPolicy(tenant.tenantId, controller.signal)
      .then((outcome) => {
        if (outcome.kind !== 'policy_loaded') return;
        const authority = resolveExternalExportAuthority(outcome.policy);
        setPolicyNotice(formatExternalExportPolicyNotice(authority));
      })
      .catch(() => {
        setPolicyNotice(formatExternalExportPolicyNotice('blocked'));
      });

    return () => controller.abort();
  }, []);

  return (
    <div className={styles.headerRow} data-trust-index-header-row>
      <header data-trust-index-header data-page-interface-header className={styles.pageHeaderStack}>
        <Typography variant="h1" className={styles.pageTitle}>
          {TRUST_ENVELOPE_INDEX_COPY.title}
        </Typography>
        <p className={styles.pageSubtitle}>{TRUST_ENVELOPE_INDEX_COPY.subtitle}</p>
      </header>
      <div className={styles.headerActionColumn}>
        {lastUpdatedAt ? (
          <div className={styles.headerMetaStack} data-trust-index-header-meta>
            <p className={styles.pageLastUpdated} data-trust-index-last-updated>
              {TRUST_ENVELOPE_INDEX_COPY.lastUpdated(formatRelativeUpdatedTime(lastUpdatedAt))}
            </p>
          </div>
        ) : null}
        <TrustEnvelopeIndexPageHeaderActions
          latestEnvelopeId={latestEnvelopeId}
          loading={loading}
          readOnly={readOnly}
        />
        {policyNotice ? (
          <p className={styles.policyNotice} data-trust-index-policy-notice role="status">
            {policyNotice}
          </p>
        ) : null}
      </div>
    </div>
  );
}
