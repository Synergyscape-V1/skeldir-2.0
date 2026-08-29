import { PageSurface } from '../components/layout/PageSurface/PageSurface';
import { Typography } from '../components/layout/Typography/Typography';
import { Card } from '../components/layout/Card/Card';
import { AuthorityBadge } from '../components/trust/AuthorityBadge/AuthorityBadge';
import { PolicyAuthorityPill, ActionRegionWithPolicy } from '../components/trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { DataUnavailablePanel } from '../components/trust/DataUnavailablePanel/DataUnavailablePanel';
import { EvidenceTimeline, CANONICAL_EVIDENCE_SEQUENCE } from '../components/trust/EvidenceTimeline/EvidenceTimeline';
import { AuditReferenceLink } from '../components/audit/AuditReferenceLink/AuditReferenceLink';
import { MemoryRouter } from 'react-router-dom';
import { ErrorBanner } from '../components/layout/ErrorBanner/ErrorBanner';
import { ResponsiveShell } from '../components/layout/ResponsiveShell/ResponsiveShell';
import { FinancialValue } from '../components/financial/FinancialValue/FinancialValue';
import { ClaimComparisonCard } from '../components/financial/ClaimComparisonCard/ClaimComparisonCard';
import { Skeleton } from '../components/layout/Skeleton/Skeleton';
import { EmptyState } from '../components/layout/EmptyState/EmptyState';
import { Toast } from '../components/layout/Toast/Toast';
import styles from './Level0SpecimenGallery.module.css';

/** Dev-only specimen gallery — not a product route */
export function Level0SpecimenGallery() {
  return (
    <PageSurface>
      <div className={styles.gallery} data-testid="level0-specimen-gallery">
        <Typography variant="h1">Skeldir Level 0 Specimen Gallery</Typography>
        <Typography variant="body">
          Substrate primitives only. No product routes. For gate evidence and visual regression.
        </Typography>

        <section className={styles.section} data-specimen="typography" aria-label="Typography specimens">
          <Typography variant="h2">Typography</Typography>
          <Typography variant="h1" data-typography="h1">H1 Specimen</Typography>
          <Typography variant="h2" data-typography="h2">H2 Specimen</Typography>
          <Typography variant="h3" data-typography="h3">H3 Specimen</Typography>
          <Typography variant="body" data-typography="body">Body specimen</Typography>
          <Typography variant="small" data-typography="small">Small specimen</Typography>
          <Typography variant="code" data-typography="code">code specimen</Typography>
        </section>

        <section className={styles.section} data-specimen="authority-badge" aria-label="Authority badge specimens">
          <Typography variant="h2">AuthorityBadge</Typography>
          <Typography variant="small">Product default (compact table chips)</Typography>
          <div className={styles.row}>
            {(['deterministic', 'probabilistic', 'benchmark', 'prior', 'unavailable', 'suppressed'] as const).map(
              (a) => (
                <AuthorityBadge key={a} authority={a} />
              ),
            )}
          </div>
          <Typography variant="small">Interactive specimen (tooltip, shield icon)</Typography>
          <div className={styles.row}>
            <AuthorityBadge authority="deterministic" size="default" showIcon />
          </div>
        </section>

        <section className={styles.section} data-specimen="policy-pill" aria-label="Policy authority pill specimens">
          <Typography variant="h2">PolicyAuthorityPill</Typography>
          <div className={styles.row}>
            <PolicyAuthorityPill state="blocked" />
            <PolicyAuthorityPill state="simulation_only" />
            <PolicyAuthorityPill state="proposal_required" />
            <PolicyAuthorityPill state="approval_required" />
          </div>
          <ActionRegionWithPolicy
            policyState="approval_required"
            actionLabel="Review claim"
            onAction={() => undefined}
          />
        </section>

        <section className={styles.section} data-specimen="unavailable-panel" aria-label="Data unavailable panel specimens">
          <Typography variant="h2">DataUnavailablePanel</Typography>
          <DataUnavailablePanel variant="no_confidence" reason="insufficient_data" />
          <DataUnavailablePanel variant="no_benchmark" reason="no_segment_coverage" />
          <DataUnavailablePanel variant="suppressed" reason="dominance_suppressed" />
          <DataUnavailablePanel variant="blocked_simulation" reason="LP_INPUT_MATRIX_UNDERDETERMINED" />
        </section>

        <section className={styles.section} data-specimen="financial-value" aria-label="Financial value specimens">
          <Typography variant="h2">FinancialValue</Typography>
          <FinancialValue amountMinor="128420" currencyCode="USD" authority="deterministic" label="Verified revenue" />
          <FinancialValue
            amountMinor={null}
            currencyCode="USD"
            authority="unavailable"
            unavailableReason="Confidence is unavailable. Deterministic verification remains active."
          />
          <AuthorityBadge authority="causal" />
        </section>

        <section className={styles.section} data-specimen="claim-comparison" aria-label="Claim comparison specimens">
          <Typography variant="h2">ClaimComparisonCard</Typography>
          <ClaimComparisonCard
            claimedRevenueMinor="900719925474099300"
            verifiedRevenueMinor="900719925474099100"
            currencyCode="USD"
            backendDifferenceMinor="200"
          />
        </section>

        <section className={styles.section} data-specimen="evidence-timeline" aria-label="Evidence timeline specimens">
          <Typography variant="h2">EvidenceTimeline</Typography>
          <EvidenceTimeline items={CANONICAL_EVIDENCE_SEQUENCE} />
        </section>

        <section className={styles.section} data-specimen="audit-reference-link" aria-label="Audit reference link specimens">
          <Typography variant="h2">AuditReferenceLink</Typography>
          <MemoryRouter>
            <AuditReferenceLink auditReference="aud_specimen_001" />
          </MemoryRouter>
        </section>

        <section className={styles.section} data-specimen="layout-states" aria-label="Layout state specimens">
          <Typography variant="h2">Layout states</Typography>
          <Card title="Loading card" state="loading_over_2s" progressCopy="Still loading verified trust state…" />
          <Skeleton rows={2} variant="row" />
          <EmptyState title="No claims match these filters." variant="filtered" onClearFilters={() => undefined} />
          <Toast severity="success" open message="Artifact exported successfully." />
        </section>

        <section className={styles.section} data-specimen="policy-conflict" aria-label="Policy conflict specimen">
          <Typography variant="h2">Policy conflict</Typography>
          <PolicyAuthorityPill state="auto_executable_within_policy" tenantPolicyMode="design_partner" />
        </section>

        <section className={styles.section} data-specimen="error-banner" aria-label="Error banner specimens">
          <Typography variant="h2">ErrorBanner</Typography>
          <ErrorBanner variant="error" />
          <ErrorBanner variant="permission_denied" />
        </section>

        <section className={styles.section} data-specimen="responsive-shell" aria-label="Responsive shell specimens">
          <Typography variant="h2">ResponsiveShell</Typography>
          <ResponsiveShell
            landmarkMode="presentational"
            viewportLabel="desktop"
            header={<span>Header primitive</span>}
            sidebar={<span>Sidebar area</span>}
          >
            <Card title="Card primitive" state="populated">
              Content gap specimen inside responsive shell main region.
            </Card>
          </ResponsiveShell>
        </section>
      </div>
    </PageSurface>
  );
}
