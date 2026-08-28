export interface ParentReturnContext {
  parentPath: string;
  parentSearch: string;
  returnLabel: string;
}

export function buildParentReturnLink(ctx: ParentReturnContext): string {
  return ctx.parentSearch ? `${ctx.parentPath}?${ctx.parentSearch.replace(/^\?/, '')}` : ctx.parentPath;
}

export const PARENT_CONTEXT_BY_SURFACE: Record<string, Omit<ParentReturnContext, 'parentSearch'>> = {
  claims: { parentPath: '/app/claims', returnLabel: 'Return to claims ledger' },
  trust: { parentPath: '/app/trust', returnLabel: 'Return to TrustEnvelope index' },
  channels: { parentPath: '/app/channels', returnLabel: 'Return to channel overview' },
  budget: { parentPath: '/app/budget', returnLabel: 'Return to budget simulation' },
  exceptions: { parentPath: '/app/exceptions', returnLabel: 'Return to exception queue' },
};

export function resolveParentContext(
  surface: keyof typeof PARENT_CONTEXT_BY_SURFACE,
  parentSearch?: string,
): ParentReturnContext {
  const base = PARENT_CONTEXT_BY_SURFACE[surface];
  return { ...base, parentSearch: parentSearch ?? '' };
}
