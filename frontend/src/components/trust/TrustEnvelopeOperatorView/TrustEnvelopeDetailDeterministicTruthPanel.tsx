import type { TrustEnvelopeDeterministicTruthData } from '../../../detail/types';
import type { TrustEnvelopeConfidenceData } from '../../../detail/types';
import { formatBpsAsPercentOneDecimal, parseMoneyMinor } from '../../../lib/money';
import { formatTrustEnvelopeMoneyMinorDisplay } from '../../../trustIndex/trustEnvelopeDetailDisplay';
import { TRUST_ENVELOPE_DETAIL_COPY } from '../../../trustIndex/trustEnvelopeDetailCopy';
import { resolveTrustEnvelopeExecutiveReliability } from '../../../trust/executiveDataReliability';
import { DataReliabilityGate } from '../DataReliabilityGate/DataReliabilityGate';
import shared from '../../../styles/shared.module.css';
import panelStyles from './TrustEnvelopeDetailPanel.module.css';
import styles from './TrustEnvelopeDetailDeterministicTruthPanel.module.css';

export interface TrustEnvelopeDetailDeterministicTruthPanelProps {
  data: TrustEnvelopeDeterministicTruthData;
  confidence: TrustEnvelopeConfidenceData;
}

function formatRateBps(rateBps: number): string {
  const body = formatBpsAsPercentOneDecimal(rateBps);
  return rateBps > 0 ? `+${body}` : body;
}

function validateDeterministicTruthIntegrity(data: TrustEnvelopeDeterministicTruthData): string | null {
  const verified = parseMoneyMinor(data.verifiedRevenueMinor);
  const claimed = parseMoneyMinor(data.claimedRevenueMinor);
  const difference = parseMoneyMinor(data.differenceMinor);
  if (!verified.ok) return verified.error;
  if (!claimed.ok) return claimed.error;
  if (!difference.ok) return difference.error;
  const computed = verified.value - claimed.value;
  if (computed !== difference.value) {
    return `Difference mismatch. Expected ${computed.toString()} minor units.`;
  }
  if (!data.commerceEvidenceSource.trim()) {
    return 'commerceEvidenceSource is required';
  }
  return null;
}

interface ComparisonColumnProps {
  label: string;
  amountMinor: bigint;
  tone: 'prior' | 'verified' | 'difference';
  rateBps?: number;
}

function ComparisonColumn({ label, amountMinor, tone, rateBps }: ComparisonColumnProps) {
  const amountDisplay = formatTrustEnvelopeMoneyMinorDisplay(amountMinor);
  const differenceSuffix =
    tone === 'difference' && rateBps !== undefined ? ` (${formatRateBps(rateBps)})` : '';

  return (
    <div className={styles.comparisonColumn} role="group" aria-label={label}>
      <span className={styles.comparisonLabel}>{label}</span>
      <span
        className={[styles.comparisonAmount, styles[`comparisonAmount_${tone}`]].join(' ')}
        data-field={tone === 'difference' ? 'difference_display' : `${tone}_amount`}
      >
        {amountDisplay}
        {differenceSuffix}
      </span>
    </div>
  );
}

export function TrustEnvelopeDetailDeterministicTruthPanel({
  data,
  confidence,
}: TrustEnvelopeDetailDeterministicTruthPanelProps) {
  const copy = TRUST_ENVELOPE_DETAIL_COPY.panels.deterministicTruth;
  const integrityError = validateDeterministicTruthIntegrity(data);
  const reliabilityResolution = resolveTrustEnvelopeExecutiveReliability({
    matchVerdictStatus: data.matchVerdictStatus,
    confidence,
    extractionFreshness: data.extractionFreshness,
  });

  if (integrityError) {
    return (
      <section className={panelStyles.panel} data-panel="deterministic-truth" role="alert">
        <div className={shared.errorState}>{integrityError}</div>
      </section>
    );
  }

  const verifiedDisplay = formatTrustEnvelopeMoneyMinorDisplay(data.verifiedRevenueMinor);

  return (
    <section
      className={panelStyles.panel}
      data-panel="deterministic-truth"
      data-trust-envelope-deterministic-truth-panel
    >
      <div className={styles.titleRow}>
        <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
      </div>

      <div className={styles.heroRow}>
        <DataReliabilityGate
          resolution={reliabilityResolution}
          amountDisplay={verifiedDisplay}
          label={copy.verifiedRevenue}
          showInlineAlert={false}
          variant="compact"
        />
      </div>

      <dl className={styles.fieldGrid}>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.currency}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-currency>
            {data.currencyCode}
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.commerceEvidenceSource}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-commerce-evidence-source>
            {data.commerceEvidenceSource}
          </dd>
        </div>
      </dl>

      <div className={styles.comparisonSection} aria-labelledby="trust-envelope-claim-comparison-heading">
        <h3 className={styles.comparisonHeading} id="trust-envelope-claim-comparison-heading">
          {copy.comparisonLabel}
        </h3>
        <div className={styles.comparisonGrid}>
          <ComparisonColumn
            label={copy.claimedRevenue}
            amountMinor={data.claimedRevenueMinor}
            tone="prior"
          />
          <ComparisonColumn
            label={copy.verifiedRevenue}
            amountMinor={data.verifiedRevenueMinor}
            tone="verified"
          />
          <ComparisonColumn
            label={copy.difference}
            amountMinor={data.differenceMinor}
            tone="difference"
            rateBps={data.differenceRateBps}
          />
        </div>
      </div>
    </section>
  );
}
