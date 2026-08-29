import { useEffect, useState } from 'react';
import { FormField } from '../../form/FormField/FormField';
import { Skeleton } from '../../layout/Skeleton/Skeleton';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { ACTIVATION_COPY } from '../../../activation/copy';
import {
  setWorkspaceConfirmed,
  setWorkspaceError,
  setWorkspaceLoading,
  setWorkspaceName,
  setWorkspaceSubmitting,
} from '../../../activation/activationStore';
import { useActivationState } from '../../../activation/useActivationState';
import { getAuthState } from '../../../auth/sessionStore';
import { getDefaultIntegrationClient } from '../../../integration/integrationClient';
import { mapIntegrationOutcomeToMessage } from '../../../integration/outcomeMapping';
import { OnboardingStepPanel } from '../OnboardingStepPanel/OnboardingStepPanel';

export function TrustWorkspaceStep() {
  const activation = useActivationState();
  const { tenant } = getAuthState();
  const [localName, setLocalName] = useState(activation.workspaceName);

  useEffect(() => {
    async function loadWorkspace() {
      if (!tenant) return;
      setWorkspaceLoading();
      const client = getDefaultIntegrationClient();
      const outcome = await client.getWorkspace(tenant.tenantId);
      if (outcome.kind === 'workspace_ready') {
        const name = outcome.workspace.workspaceName || tenant.workspaceName;
        setLocalName(name);
        setWorkspaceName(name);
        if (outcome.workspace.activationStatus === 'confirmed') {
          setWorkspaceConfirmed(name);
        }
      } else {
        setLocalName(tenant.workspaceName);
        setWorkspaceName(tenant.workspaceName);
      }
    }
    void loadWorkspace();
  }, [tenant]);

  if (activation.workspaceStatus === 'loading') {
    return (
      <OnboardingStepPanel heading={ACTIVATION_COPY.step1.heading} body={ACTIVATION_COPY.step1.body}>
        <Skeleton rows={3} variant="block" />
      </OnboardingStepPanel>
    );
  }

  return (
    <OnboardingStepPanel heading={ACTIVATION_COPY.step1.heading} body={ACTIVATION_COPY.step1.body}>
      <FormField
        id="workspace-name"
        label={ACTIVATION_COPY.step1.workspaceNameLabel}
        value={localName}
        onChange={(event) => {
          setLocalName(event.target.value);
          setWorkspaceName(event.target.value);
        }}
        disabled={activation.workspaceStatus === 'submitting'}
        error={
          activation.workspaceStatus === 'invalid'
            ? ACTIVATION_COPY.step1.continueBlocked
            : activation.workspaceError
        }
      />
      {tenant ? (
        <p>
          <strong>{ACTIVATION_COPY.step1.tenantContextLabel}:</strong> {tenant.tenantId} —{' '}
          {tenant.workspaceName}
        </p>
      ) : null}
      {activation.workspaceStatus === 'success' ? (
        <p role="status" aria-live="polite">
          {ACTIVATION_COPY.step1.success}
        </p>
      ) : null}
      {activation.workspaceStatus === 'error' && activation.workspaceError ? (
        <ErrorBanner message={activation.workspaceError} />
      ) : null}
    </OnboardingStepPanel>
  );
}

export async function submitWorkspaceStep(workspaceName: string): Promise<boolean> {
  const { tenant } = getAuthState();
  if (!tenant || workspaceName.trim().length < 2) {
    setWorkspaceError(ACTIVATION_COPY.step1.continueBlocked);
    return false;
  }
  setWorkspaceSubmitting();
  const client = getDefaultIntegrationClient();
  const outcome = await client.confirmWorkspace(tenant.tenantId, workspaceName.trim());
  if (outcome.kind === 'workspace_ready') {
    setWorkspaceConfirmed(outcome.workspace.workspaceName);
    return true;
  }
  setWorkspaceError(
    mapIntegrationOutcomeToMessage(outcome) || ACTIVATION_COPY.step1.error,
  );
  return false;
}
