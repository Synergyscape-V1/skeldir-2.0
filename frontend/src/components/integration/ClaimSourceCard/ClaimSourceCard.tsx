import { INTEGRATION_COPY } from '../../../integration/copy';
import type { ClaimProvider, IntegrationSourceState } from '../../../integration/types';
import { IntegrationSourceCard } from '../IntegrationSourceCard/IntegrationSourceCard';

export interface ClaimSourceCardProps {
  state: IntegrationSourceState;
  onConnect: (provider: ClaimProvider) => Promise<void>;
  onRepair: (provider: ClaimProvider) => Promise<void>;
}

export function ClaimSourceCard({ state, onConnect, onRepair }: ClaimSourceCardProps) {
  return (
    <IntegrationSourceCard
      state={state}
      onConnect={(provider) => onConnect(provider as ClaimProvider)}
      onRepair={(provider) => onRepair(provider as ClaimProvider)}
      authorityCopy={INTEGRATION_COPY.claimSourceCopy}
      showLastClaim
      showReconciliation
    />
  );
}
