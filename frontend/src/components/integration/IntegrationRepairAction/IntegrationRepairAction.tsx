import { IntegrationActionButton } from '../IntegrationActionButton/IntegrationActionButton';

export interface IntegrationRepairActionProps {
  onRepair: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export function IntegrationRepairAction({ onRepair, loading, disabled }: IntegrationRepairActionProps) {
  return (
    <IntegrationActionButton action="repair" loading={loading} disabled={disabled} onClick={onRepair} />
  );
}
