import { INTEGRATION_COPY } from '../../../integration/copy';
import type { CommerceProvider, IntegrationSourceState } from '../../../integration/types';
import { IntegrationSourceCard } from '../IntegrationSourceCard/IntegrationSourceCard';

export interface CommerceSourceCardProps {
  state: IntegrationSourceState;
  onConnect: (provider: CommerceProvider) => Promise<void>;
  onRepair: (provider: CommerceProvider) => Promise<void>;
}

export function CommerceSourceCard({ state, onConnect, onRepair }: CommerceSourceCardProps) {
  return (
    <IntegrationSourceCard
      state={state}
      onConnect={(provider) => onConnect(provider as CommerceProvider)}
      onRepair={(provider) => onRepair(provider as CommerceProvider)}
      authorityCopy={INTEGRATION_COPY.commerceAuthorityCopy}
      showLastEvent
      showVerification
    />
  );
}
