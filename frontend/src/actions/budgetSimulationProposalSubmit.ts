import { getDefaultBudgetProposalClient } from './budgetProposalClient';
import type { GovernedActionOutcome } from './types';

/** L9 proposal submit port — keeps budget/ layer free of direct action client symbols. */
export async function executeSimulationProposalSubmit(
  tenantId: string,
  simulationId: string,
  versionStamp: string,
  idempotencyKey: string,
): Promise<GovernedActionOutcome> {
  return getDefaultBudgetProposalClient().submitBudgetProposal(
    tenantId,
    simulationId,
    versionStamp,
    idempotencyKey,
  );
}
