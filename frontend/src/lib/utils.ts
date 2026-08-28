export function escapeText(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function isKnownAuthority(value: string): boolean {
  return (
    value === 'deterministic' ||
    value === 'probabilistic' ||
    value === 'benchmark' ||
    value === 'prior' ||
    value === 'unavailable' ||
    value === 'suppressed'
  );
}

export function isKnownPolicyState(value: string): boolean {
  return (
    value === 'blocked' ||
    value === 'simulation_only' ||
    value === 'proposal_required' ||
    value === 'approval_required' ||
    value === 'auto_executable_within_policy'
  );
}

export function classNames(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

