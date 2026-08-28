import type { ExecutiveDataReliability, ExecutiveReliabilityVariant } from './executiveDataReliability';

export const EXECUTIVE_RELIABILITY_COPY = {
  badge: {
    verified: 'Verified',
    estimated: 'Estimated',
    pending: 'Pending',
    unavailable: 'Unavailable',
    discrepancy: 'Discrepancy',
  },
  tooltip: {
    verified:
      'Deterministic match confirmed. Statistical confidence is available where applicable.',
    estimated:
      'This figure is based on incomplete or delayed source data. It is an estimate, not verified financial truth.',
    pending: 'Commerce data delayed. System will retry. No action needed.',
    unavailable: 'Connect or repair your commerce source to enable verification.',
    discrepancy:
      'The platform is claiming credit for revenue our commerce records do not confirm. Investigate before relying on this figure.',
  },
  headline: {
    verified: 'Verified',
    estimated: 'Data extraction is currently degraded.',
    pending: 'Checking',
    unavailable: 'Unavailable',
    discrepancy: 'Discrepancy detected',
  },
  body: {
    verified:
      'Revenue confirmed against commerce data with high statistical confidence.',
    estimated:
      'Skeldir could not fully verify this claim against commerce evidence due to a source connection issue. This number is an estimate and has been locked from budget simulations and financial exports to protect your reporting accuracy.',
    pending: 'Commerce data delayed. Automatic retry active.',
    unavailable: 'Commerce data could not be verified.',
    discrepancy:
      'The platform claim actively contradicts the commerce evidence beyond the acceptable variance threshold. This claim is locked from budget simulations and exports and flagged for investigation.',
  },
  variant: {
    matched_provisional: {
      badge: 'Awaiting confirmation',
      headline: 'Awaiting confirmation',
      body: 'Initial match found. Final verification pending.',
      tooltip: 'Commerce event detected. Confirmation typically completes within 24 hours.',
    },
    confidence_building: {
      badge: 'Estimated',
      headline: 'Estimated',
      body: 'Revenue verified against commerce data. Statistical confidence building.',
      tooltip:
        'We need more verified transactions before showing a confidence range. Deterministic verification is active.',
    },
    confidence_paused: {
      badge: 'Confidence paused',
      headline: 'Confidence paused',
      body: 'Statistical model timed out. Deterministic verification remains active.',
      tooltip: 'Retry scheduled automatically. Contact support if this persists >24h.',
    },
    confidence_updating: {
      badge: 'Confidence updating',
      headline: 'Confidence updating',
      body: 'Statistical model did not converge. Deterministic verification remains active.',
      tooltip: 'Model recalculation scheduled. No action needed.',
    },
    flagged: {
      badge: 'Discrepancy',
      headline: 'Discrepancy detected',
      body: 'This claim exceeds the acceptable variance threshold between the platform claim and commerce evidence. Investigate before relying on this figure.',
      tooltip: 'Platform claim and commerce evidence diverge. Marked for review before use in reporting.',
    },
    material: {
      badge: 'Discrepancy',
      headline: 'Material discrepancy',
      body: 'This claim exceeds the material variance threshold: the platform is claiming revenue we did not collect. Investigate immediately.',
      tooltip: 'Platform claim contradicts commerce evidence beyond the material threshold. Treat as a potential revenue overstatement.',
    },
  },
  permissions: {
    simulatorBlocked: 'Cannot simulate budget based on estimated data.',
    exportBlocked:
      'This claim is based on estimated data and cannot be included in a verified export.',
    discrepancyExportBlocked:
      'This claim has an unresolved discrepancy and cannot be included in a verified export.',
    exportExcludedToast: (count: number) =>
      `${count} estimated claim${count === 1 ? '' : 's'} excluded from your verified report.`,
  },
  repairLink: 'Repair source connection',
  repairHref: '/app/integrations',
} as const;

export function executiveReliabilityBadgeLabel(
  reliability: ExecutiveDataReliability,
  variant?: ExecutiveReliabilityVariant,
): string {
  if (variant === 'matched_provisional') {
    return EXECUTIVE_RELIABILITY_COPY.variant.matched_provisional.badge;
  }
  if (variant === 'confidence_paused') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_paused.badge;
  }
  if (variant === 'confidence_updating') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_updating.badge;
  }
  if (variant === 'confidence_building' && reliability === 'estimated') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_building.badge;
  }
  if ((variant === 'flagged' || variant === 'material') && reliability === 'discrepancy') {
    return EXECUTIVE_RELIABILITY_COPY.variant[variant].badge;
  }
  return EXECUTIVE_RELIABILITY_COPY.badge[reliability];
}

export function executiveReliabilityTooltip(
  reliability: ExecutiveDataReliability,
  variant?: ExecutiveReliabilityVariant,
): string {
  if (variant === 'matched_provisional') {
    return EXECUTIVE_RELIABILITY_COPY.variant.matched_provisional.tooltip;
  }
  if (variant === 'confidence_paused') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_paused.tooltip;
  }
  if (variant === 'confidence_updating') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_updating.tooltip;
  }
  if (variant === 'confidence_building' && reliability === 'estimated') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_building.tooltip;
  }
  if ((variant === 'flagged' || variant === 'material') && reliability === 'discrepancy') {
    return EXECUTIVE_RELIABILITY_COPY.variant[variant].tooltip;
  }
  return EXECUTIVE_RELIABILITY_COPY.tooltip[reliability];
}

export function executiveReliabilityAlertHeadline(
  reliability: ExecutiveDataReliability,
  variant?: ExecutiveReliabilityVariant,
): string | null {
  if (reliability === 'verified') return null;
  if (variant === 'matched_provisional') {
    return EXECUTIVE_RELIABILITY_COPY.variant.matched_provisional.headline;
  }
  if (variant === 'confidence_paused') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_paused.headline;
  }
  if (variant === 'confidence_updating') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_updating.headline;
  }
  if ((variant === 'flagged' || variant === 'material') && reliability === 'discrepancy') {
    return EXECUTIVE_RELIABILITY_COPY.variant[variant].headline;
  }
  return EXECUTIVE_RELIABILITY_COPY.headline[reliability];
}

export function executiveReliabilityAlertBody(
  reliability: ExecutiveDataReliability,
  variant?: ExecutiveReliabilityVariant,
): string | null {
  if (reliability === 'verified') return null;
  if (variant === 'matched_provisional') {
    return EXECUTIVE_RELIABILITY_COPY.variant.matched_provisional.body;
  }
  if (variant === 'confidence_paused') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_paused.body;
  }
  if (variant === 'confidence_updating') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_updating.body;
  }
  if (variant === 'confidence_building' && reliability === 'estimated') {
    return EXECUTIVE_RELIABILITY_COPY.variant.confidence_building.body;
  }
  if ((variant === 'flagged' || variant === 'material') && reliability === 'discrepancy') {
    return EXECUTIVE_RELIABILITY_COPY.variant[variant].body;
  }
  return EXECUTIVE_RELIABILITY_COPY.body[reliability];
}
