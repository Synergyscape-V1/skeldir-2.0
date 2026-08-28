import { Link } from 'react-router-dom';

import { FIRST_TRUST_ENVELOPE_COPY } from '../../../firstTrustEnvelope/copy';

import {
  buildAuditReferenceLabel,
  buildTrustEnvelopeAuditReferenceHref,
} from '../../../firstTrustEnvelope/auditReference';

import { hasProbabilisticConfidenceShape } from '../../../firstTrustEnvelope/summaryValidation';

import type { FirstTrustEnvelopeSummary as SummaryType } from '../../../firstTrustEnvelope/types';

import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';

import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';

import { DataUnavailablePanel } from '../../trust/DataUnavailablePanel/DataUnavailablePanel';

import { FinancialValue } from '../../financial/FinancialValue/FinancialValue';

import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';

import styles from './FirstTrustEnvelopeSummary.module.css';



export interface FirstTrustEnvelopeSummaryProps {

  envelope: SummaryType;

}



function ConfidenceRegion({ envelope }: { envelope: SummaryType }) {

  if (envelope.confidenceStatus === 'unavailable' || envelope.confidenceStatus === 'delayed') {

    return (

      <DataUnavailablePanel

        variant="no_confidence"

        reason={envelope.confidenceReason}

        whatStillWorks="Deterministic verification remains active."

      />

    );

  }



  if (!hasProbabilisticConfidenceShape(envelope)) {

    return (

      <ErrorBanner message={FIRST_TRUST_ENVELOPE_COPY.step5.nakedScalarConfidence} />

    );

  }



  return (

    <div className={styles.confidenceShape}>

      {envelope.confidenceReason ? (

        <p className={styles.confidenceReason}>{envelope.confidenceReason}</p>

      ) : null}

      {envelope.confidenceMethodOrContext ? (

        <p className={styles.confidenceMeta}>

          <span className={styles.metaLabel}>Method</span>

          {envelope.confidenceMethodOrContext}

        </p>

      ) : null}

      {envelope.credibleInterval ? (

        <p className={styles.interval}>{envelope.credibleInterval}</p>

      ) : null}

      {envelope.intervalLower !== undefined && envelope.intervalUpper !== undefined ? (

        <p className={styles.intervalNumeric}>

          Interval {envelope.intervalLower} – {envelope.intervalUpper}

        </p>

      ) : null}

      {envelope.uncertaintyBand ? (

        <p className={styles.uncertainty}>{envelope.uncertaintyBand}</p>

      ) : null}

      {envelope.qualitativeProbabilisticState ? (

        <p className={styles.qualitativeState}>{envelope.qualitativeProbabilisticState}</p>

      ) : null}

      {envelope.sampleOrSourceContext ? (

        <p className={styles.confidenceMeta}>

          <span className={styles.metaLabel}>Source</span>

          {envelope.sampleOrSourceContext}

        </p>

      ) : null}

      {envelope.confidenceAuthority ? (

        <AuthorityBadge authority={envelope.confidenceAuthority} />

      ) : null}

    </div>

  );

}



export function FirstTrustEnvelopeSummary({ envelope }: FirstTrustEnvelopeSummaryProps) {

  if (!envelope.auditEventId) {

    return (

      <ErrorBanner message={FIRST_TRUST_ENVELOPE_COPY.summary.missingAuditReference} />

    );

  }



  const auditHref = buildTrustEnvelopeAuditReferenceHref(
    envelope.auditEventId,
    envelope.envelopeId,
  );



  return (

    <section className={styles.summary} data-first-trust-envelope-summary aria-label="First TrustEnvelope summary">

      <div className={styles.primaryRegion} data-authority-tier="deterministic-primary">

        <h2 className={styles.primaryHeading}>{FIRST_TRUST_ENVELOPE_COPY.summary.verifiedRevenue}</h2>

        <FinancialValue

          label={FIRST_TRUST_ENVELOPE_COPY.summary.verifiedRevenue}

          amountMinor={envelope.verifiedRevenueMinor}

          currencyCode={envelope.currencyCode}

          authority={envelope.revenueAuthority}

        />

        <p className={styles.subjectRef}>

          <span className={styles.label}>{FIRST_TRUST_ENVELOPE_COPY.summary.subjectRef}</span>

          <span className={styles.value}>{envelope.subjectRef}</span>

        </p>

      </div>



      <div className={styles.subordinateRegion} data-authority-tier="model-output">

        <h3 className={styles.subordinateHeading}>{FIRST_TRUST_ENVELOPE_COPY.summary.attributionModel}</h3>

        <p className={styles.value}>{envelope.attributionModel}</p>

        <AuthorityBadge authority={envelope.attributionAuthority} label="Model output" />

        <p className={styles.attributionNote}>{FIRST_TRUST_ENVELOPE_COPY.step5.attributionNote}</p>

      </div>



      <div className={styles.subordinateRegion} data-authority-tier="probabilistic-subordinate">

        <h3 className={styles.subordinateHeading}>{FIRST_TRUST_ENVELOPE_COPY.summary.confidence}</h3>

        <ConfidenceRegion envelope={envelope} />

      </div>



      {envelope.benchmarkStatus === 'unavailable' && envelope.benchmarkReason ? (

        <div className={styles.subordinateRegion} data-authority-tier="benchmark-subordinate">

          <DataUnavailablePanel variant="no_benchmark" reason={envelope.benchmarkReason} />

        </div>

      ) : null}



      <div className={styles.governanceRegion} data-authority-tier="policy-governance">

        <h3 className={styles.subordinateHeading}>{FIRST_TRUST_ENVELOPE_COPY.summary.policyAuthority}</h3>

        <PolicyAuthorityPill state={envelope.policyAuthority} />

      </div>



      <div className={styles.auditRegion} data-authority-tier="audit-reference">

        <h3 className={styles.subordinateHeading}>{FIRST_TRUST_ENVELOPE_COPY.summary.auditReference}</h3>

        <Link

          to={auditHref}

          className={styles.auditLink}

          aria-label={buildAuditReferenceLabel(envelope.auditEventId)}

        >

          {buildAuditReferenceLabel(envelope.auditEventId)}

        </Link>

      </div>



      <div className={styles.metadataRegion} data-authority-tier="metadata-subordinate">

        <h3 className={styles.metadataHeading}>{FIRST_TRUST_ENVELOPE_COPY.summary.envelopeId}</h3>

        <code className={styles.mono}>{envelope.envelopeId}</code>

        <p className={styles.generatedAt}>

          <span className={styles.label}>{FIRST_TRUST_ENVELOPE_COPY.summary.generatedAt}</span>

          <time className={styles.value} dateTime={envelope.generatedAt}>

            {envelope.generatedAt}

          </time>

        </p>

      </div>

    </section>

  );

}

