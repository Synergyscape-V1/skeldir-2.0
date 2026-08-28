import type { TrustEnvelopeDetailDTO } from '../../../detail/types';
import { TrustEnvelopeDetailVerdictSummary } from './TrustEnvelopeDetailVerdictSummary';
import { TrustEnvelopeDetailSubjectPanel } from './TrustEnvelopeDetailSubjectPanel';
import { TrustEnvelopeDetailDeterministicTruthPanel } from './TrustEnvelopeDetailDeterministicTruthPanel';
import { TrustEnvelopeDetailAttributionPanel } from './TrustEnvelopeDetailAttributionPanel';
import { TrustEnvelopeDetailConfidencePanel } from './TrustEnvelopeDetailConfidencePanel';
import { TrustEnvelopeDetailPolicyAuthorityPanel } from './TrustEnvelopeDetailPolicyAuthorityPanel';
import { TrustEnvelopeDetailAuditPanel } from './TrustEnvelopeDetailAuditPanel';
import styles from './TrustEnvelopeOperatorContent.module.css';

export interface TrustEnvelopeOperatorContentProps {
  detail: TrustEnvelopeDetailDTO;
}

export function TrustEnvelopeOperatorContent({ detail }: TrustEnvelopeOperatorContentProps) {
  return (
    <div className={styles.content} data-trust-envelope-operator-view>
      <TrustEnvelopeDetailVerdictSummary detail={detail} />
      <div className={styles.panels} data-trust-human-panels data-trust-room="storyboard">
        <TrustEnvelopeDetailSubjectPanel subject={detail.subject} />
        <TrustEnvelopeDetailDeterministicTruthPanel
          data={detail.deterministicTruth}
          confidence={detail.confidence}
        />
        <TrustEnvelopeDetailAttributionPanel data={detail.attribution} />
        <TrustEnvelopeDetailConfidencePanel
          data={detail.confidence}
          benchmark={detail.benchmark}
          referenceAt={detail.createdAt}
        />
        <TrustEnvelopeDetailPolicyAuthorityPanel data={detail.policyAuthority} />
        <TrustEnvelopeDetailAuditPanel auditReference={detail.auditReference} envelopeId={detail.envelopeId} />
      </div>
    </div>
  );
}
