import { useCallback, useEffect, useRef, useState } from 'react';

import { getActivationState, setGenerationPhase, setFirstEnvelopeSummary } from '../activation/activationStore';

import { getAuthState } from '../auth/sessionStore';

import { getCurrentUserRole } from '../governance/governanceStore';

import { useIntegrations } from '../integration/useIntegrations';

import { getDefaultOperationalAuditClient } from '../operationalAudit/operationalAuditClient';

import {

  getDefaultFirstTrustEnvelopeClient,

  hasVerifiedCommerceEvent,

} from './firstTrustEnvelopeClient';

import {

  mapGenerationOutcomeToMessage,

  mapReadinessOutcomeToMessage,

} from './outcomeMapping';

import { persistIdempotencyKey, resolveIdempotencyKey } from './idempotency';

import {

  canAttemptGeneration,

  isGenerationErrorPhase,

  mapGenerationOutcomeToPhase,

  resolveStep5PrerequisiteState,

} from './step5StateMachine';

import type { GenerationPrerequisites, Step5PrerequisiteState } from './types';



async function checkAuditSubstrate(tenantId: string): Promise<boolean> {

  const client = getDefaultOperationalAuditClient();

  const outcome = await client.listAuditEvents(tenantId, {});

  return outcome.kind === 'audit_loaded' || outcome.kind === 'audit_empty';

}



export function useFirstTrustEnvelopeGeneration() {

  const { integrations, commerceReady } = useIntegrations();

  const activation = getActivationState();

  const [prerequisiteState, setPrerequisiteState] = useState<Step5PrerequisiteState>('locked_by_workspace');

  const [statusMessage, setStatusMessage] = useState('');

  const [submitLocked, setSubmitLocked] = useState(false);

  const [loadingReadiness, setLoadingReadiness] = useState(true);

  const generateInFlight = useRef(false);



  const buildPrerequisites = useCallback((): GenerationPrerequisites => {

    return {

      workspaceConfirmed: activation.workspaceConfirmed,

      commerceReady,

      privacyConfirmed: activation.privacyStatus === 'confirmed',

      policyAvailable: getCurrentUserRole() !== 'unknown_role',

      auditSubstrateAvailable: activation.auditSubstrateAvailable,

      verifiedCommerceEventAvailable: hasVerifiedCommerceEvent(integrations),

    };

  }, [activation.workspaceConfirmed, activation.privacyStatus, activation.auditSubstrateAvailable, commerceReady, integrations]);



  useEffect(() => {

    let cancelled = false;

    async function loadReadiness() {

      setLoadingReadiness(true);

      const { tenant } = getAuthState();

      if (!tenant) {

        setPrerequisiteState('locked_by_workspace');

        setLoadingReadiness(false);

        return;

      }



      let auditAvailable = activation.auditSubstrateAvailable;

      if (!auditAvailable) {

        auditAvailable = await checkAuditSubstrate(tenant.tenantId);

      }



      const prerequisites: GenerationPrerequisites = {

        ...buildPrerequisites(),

        auditSubstrateAvailable: auditAvailable,

      };

      const state = resolveStep5PrerequisiteState(prerequisites);

      if (cancelled) return;

      setPrerequisiteState(state);



      const client = getDefaultFirstTrustEnvelopeClient();

      const outcome = await client.checkReadiness(tenant.tenantId, prerequisites);

      if (cancelled) return;

      setStatusMessage(mapReadinessOutcomeToMessage(outcome));



      const existing = await client.getExistingFirstEnvelope(tenant.tenantId);

      if (cancelled) return;

      if (existing) {

        setFirstEnvelopeSummary(existing);

        setGenerationPhase('generation_already_exists');

      }

      setLoadingReadiness(false);

    }

    void loadReadiness();

    return () => {

      cancelled = true;

    };

  }, [activation.auditSubstrateAvailable, buildPrerequisites]);



  const generate = useCallback(async () => {

    if (generateInFlight.current || submitLocked) return;

    const { tenant } = getAuthState();

    if (!tenant) return;



    const prerequisites = buildPrerequisites();

    const state = resolveStep5PrerequisiteState(prerequisites);

    if (!canAttemptGeneration(state)) {

      setStatusMessage(mapReadinessOutcomeToMessage({ kind: 'first_envelope_unavailable', reason: state }));

      return;

    }



    generateInFlight.current = true;

    setSubmitLocked(true);

    setGenerationPhase('generation_queued');

    setStatusMessage(mapGenerationOutcomeToMessage({ kind: 'first_envelope_generation_started', requestId: 'pending' }));



    const idempotencyKey = resolveIdempotencyKey(tenant.tenantId);

    persistIdempotencyKey(tenant.tenantId, idempotencyKey);



    const client = getDefaultFirstTrustEnvelopeClient();

    setGenerationPhase('generation_in_progress');

    const outcome = await client.generateFirstEnvelope(tenant.tenantId, idempotencyKey);

    const phase = mapGenerationOutcomeToPhase(outcome.kind);

    setGenerationPhase(phase);

    setStatusMessage(mapGenerationOutcomeToMessage(outcome));



    if (

      outcome.kind === 'first_envelope_generated' ||

      outcome.kind === 'first_envelope_already_exists'

    ) {

      setFirstEnvelopeSummary(outcome.envelope);

    }



    generateInFlight.current = false;

    if (isGenerationErrorPhase(phase)) {

      setSubmitLocked(false);

    }

  }, [buildPrerequisites, submitLocked]);



  return {

    prerequisiteState,

    statusMessage,

    submitLocked,

    loadingReadiness,

    canGenerate: canAttemptGeneration(prerequisiteState) && !submitLocked && !loadingReadiness,

    generate,

  };

}

