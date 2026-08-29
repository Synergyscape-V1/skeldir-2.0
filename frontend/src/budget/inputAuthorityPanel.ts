import { BUDGET_SUFFICIENCY_THRESHOLDS } from './budgetFixtures';
import { BUDGET_SIMULATION_COPY } from './copy';
import type { SufficiencySummary } from './budgetSimulationTypes';

export type InputAuthorityChipTone = 'success' | 'error' | 'warning' | 'neutral';

export interface InputAuthorityFact {
  term: string;
  detail: string;
}

export interface InputAuthorityPresentation {
  panelTone: 'eligible' | 'blocked' | 'partial' | 'loading' | 'neutral';
  chipTone: InputAuthorityChipTone;
  statusLabel: string;
  intro: string;
  facts: InputAuthorityFact[];
}

export function resolveInputAuthorityPresentation(
  summary: SufficiencySummary,
  channelCount: number,
  verifiedConversions: number,
  trustApiOperational: boolean,
): InputAuthorityPresentation {
  const { state } = summary;
  const { minimumChannels, minimumVerifiedConversions } = BUDGET_SUFFICIENCY_THRESHOLDS;
  const copy = BUDGET_SIMULATION_COPY.inputAuthority;
  const generateAllowed = state === 'eligible' || state === 'partial';
  const deterministicPresent = state === 'eligible' || state === 'partial';

  const baseFacts: InputAuthorityFact[] = [
    {
      term: copy.deterministicEvidence,
      detail: deterministicPresent ? copy.yes : copy.no,
    },
    {
      term: copy.verifiedChannels,
      detail: String(channelCount),
    },
    {
      term: copy.verifiedConversions,
      detail: String(verifiedConversions),
    },
    {
      term: copy.trustApiState,
      detail: trustApiOperational ? copy.operational : copy.unavailable,
    },
    {
      term: copy.actionAuthority,
      detail: generateAllowed ? copy.generateAllowed : copy.actionBlocked,
    },
    {
      term: copy.submissionGated,
      detail: copy.yes,
    },
  ];

  const thresholdFacts: InputAuthorityFact[] = [
    { term: copy.minimumChannelsRequired, detail: String(minimumChannels) },
    { term: copy.channelsAvailable, detail: String(channelCount) },
    { term: copy.minimumConversionsRequired, detail: String(minimumVerifiedConversions) },
    { term: copy.conversionsAvailable, detail: String(verifiedConversions) },
    { term: copy.actionAuthority, detail: copy.actionBlocked },
  ];

  switch (state) {
    case 'eligible':
      return {
        panelTone: 'eligible',
        chipTone: 'success',
        statusLabel: copy.eligible,
        intro: copy.introEligible,
        facts: baseFacts,
      };
    case 'partial':
      return {
        panelTone: 'partial',
        chipTone: 'warning',
        statusLabel: copy.statusPartial,
        intro: copy.introPartial,
        facts: baseFacts,
      };
    case 'blocked':
      return {
        panelTone: 'blocked',
        chipTone: 'error',
        statusLabel: copy.ineligible,
        intro: copy.introIneligible,
        facts: thresholdFacts,
      };
    case 'error':
      return {
        panelTone: 'blocked',
        chipTone: 'error',
        statusLabel: copy.statusError,
        intro: copy.introError,
        facts: baseFacts,
      };
    case 'loading':
      return {
        panelTone: 'loading',
        chipTone: 'neutral',
        statusLabel: copy.statusLoading,
        intro: copy.introLoading,
        facts: baseFacts,
      };
    case 'empty':
    default:
      return {
        panelTone: 'neutral',
        chipTone: 'neutral',
        statusLabel: copy.statusEmpty,
        intro: copy.introEmpty,
        facts: baseFacts,
      };
  }
}
