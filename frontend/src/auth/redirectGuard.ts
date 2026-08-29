/** Safe post-auth redirect resolution — fail closed on unsafe targets */



export const LEVEL1_PERMITTED_ROUTES = [

  '/login',

  '/signup',

  '/auth',

  '/entry/session-ready',

  '/entry/workspace-created',

  '/dev/specimens',

  '/dev/auth-specimens',

  '/dev/shell-specimens',

] as const;



/** Level 2 shell frame routes — not downstream product surfaces */

export const LEVEL2_SHELL_ROUTES = ['/app', '/shell'] as const;



/** Level 3 activation routes — permitted with session + tenant */
export const LEVEL3_PERMITTED_ROUTES = ['/onboarding', '/integrations'] as const;

/** Level 4 governance routes — permitted with session + tenant */
export const LEVEL4_PERMITTED_ROUTES = [
  '/settings/team',
  '/settings/policy',
] as const;

/** Level 5 operational/audit routes — permitted with session + tenant */
export const LEVEL5_PERMITTED_ROUTES = ['/audit', '/diagnostics'] as const;

/** Level 7 primary ledger routes — permitted with session + tenant */
export const LEVEL7_PERMITTED_ROUTES = [
  '/claims',
  '/trust',
  '/channels',
  '/budget',
  '/exceptions',
] as const;

/** Level 11 launch-parity routes — permitted with session + tenant */
export const LEVEL11_PERMITTED_ROUTES = ['/settings/billing'] as const;

/** Level 8+ detail routes that were blocked before implementation — kept empty after Level 11 */
export const LEVEL8_PLUS_BLOCKED_ROUTES = [] as const;

/** Routes blocked until Level 7 was implemented — kept for regression tests */
export const LEVEL6_PLUS_BLOCKED_ROUTES = [] as const;

/** @deprecated Use LEVEL6_PLUS_BLOCKED_ROUTES */
export const LEVEL5_PLUS_BLOCKED_ROUTES = LEVEL6_PLUS_BLOCKED_ROUTES;

/** @deprecated Use LEVEL5_PLUS_BLOCKED_ROUTES */
export const LEVEL4_PLUS_BLOCKED_ROUTES = LEVEL5_PLUS_BLOCKED_ROUTES;



/** @deprecated Use LEVEL5_PLUS_BLOCKED_ROUTES */
export const LEVEL2_PLUS_BLOCKED_ROUTES = LEVEL5_PLUS_BLOCKED_ROUTES;



export type RedirectRejectionReason =

  | 'external'

  | 'javascript'

  | 'unknown'

  | 'level4_blocked'

  | 'level2_blocked'

  | 'tenant_required'

  | 'session_required'

  | 'onboarding_premature';



export interface RedirectContext {

  hasSession: boolean;

  hasTenant: boolean;

}



export interface SafeRedirectResult {

  ok: true;

  path: string;

}



export interface UnsafeRedirectResult {

  ok: false;

  reason: RedirectRejectionReason;

}



export type RedirectResolution = SafeRedirectResult | UnsafeRedirectResult;



function normalizePath(raw: string): string {

  const trimmed = raw.trim();

  if (!trimmed.startsWith('/')) return `/${trimmed}`;

  return trimmed.split('?')[0]?.split('#')[0] ?? trimmed;

}



function isExternalUrl(value: string): boolean {

  return /^https?:\/\//i.test(value) || /^\/\//.test(value);

}



function isJavascriptUrl(value: string): boolean {

  return /^javascript:/i.test(value.trim());

}



function isShellRoute(path: string): boolean {

  return (

    path === '/app' ||

    path === '/shell' ||

    path.startsWith('/app/') ||

    path.startsWith('/shell/')

  );

}



function isLevel11Permitted(path: string): boolean {
  return LEVEL11_PERMITTED_ROUTES.some(
    (permitted) => path === permitted || path.startsWith(`${permitted}/`),
  );
}

function isAppBillingPath(path: string): boolean {
  return path === '/settings/billing' || path.startsWith('/settings/billing/') || path.startsWith('/app/settings/billing');
}

function matchesLevel8Blocked(path: string): boolean {
  return LEVEL8_PLUS_BLOCKED_ROUTES.some(
    (blocked) => path === blocked || path.startsWith(`${blocked}/`),
  );
}

function isLevel7Permitted(path: string): boolean {
  return LEVEL7_PERMITTED_ROUTES.some(
    (permitted) => path === permitted || path.startsWith(`${permitted}/`),
  );
}

function isAppLedgerPath(path: string): boolean {
  return (
    path.startsWith('/app/claims') ||
    path.startsWith('/app/trust') ||
    path.startsWith('/app/channels') ||
    path.startsWith('/app/budget') ||
    path.startsWith('/app/exceptions') ||
    path === '/claims' ||
    path.startsWith('/claims/') ||
    path === '/trust' ||
    path.startsWith('/trust/') ||
    path === '/channels' ||
    path.startsWith('/channels/') ||
    path === '/budget' ||
    path.startsWith('/budget/') ||
    path === '/exceptions' ||
    path.startsWith('/exceptions/')
  );
}

function matchesLevel6Blocked(path: string): boolean {
  return LEVEL6_PLUS_BLOCKED_ROUTES.some(
    (blocked) => path === blocked || path.startsWith(`${blocked}/`),
  );
}

function isLevel5Permitted(path: string): boolean {
  return LEVEL5_PERMITTED_ROUTES.some(
    (permitted) => path === permitted || path.startsWith(`${permitted}/`),
  );
}

function isAppOperationalAuditPath(path: string): boolean {
  return (
    path.startsWith('/app/audit') ||
    path.startsWith('/app/diagnostics') ||
    path === '/audit' ||
    path.startsWith('/audit/') ||
    path === '/diagnostics' ||
    path.startsWith('/diagnostics/')
  );
}

function isLevel4Permitted(path: string): boolean {
  return LEVEL4_PERMITTED_ROUTES.some(
    (permitted) => path === permitted || path.startsWith(`${permitted}/`),
  );
}

function isAppGovernancePath(path: string): boolean {
  return (
    path.startsWith('/app/settings/') ||
    path === '/settings/team' ||
    path.startsWith('/settings/team/') ||
    path === '/settings/policy' ||
    path.startsWith('/settings/policy/')
  );
}

function isLevel3Permitted(path: string): boolean {
  return LEVEL3_PERMITTED_ROUTES.some(
    (permitted) => path === permitted || path.startsWith(`${permitted}/`),
  );
}

function isAppActivationPath(path: string): boolean {
  return (
    path.startsWith('/app/onboarding') ||
    path.startsWith('/app/integrations') ||
    path === '/onboarding' ||
    path.startsWith('/onboarding/') ||
    path === '/integrations' ||
    path.startsWith('/integrations/')
  );
}

function isKnownPermitted(path: string): boolean {
  if (LEVEL1_PERMITTED_ROUTES.some((permitted) => path === permitted || path.startsWith(`${permitted}/`))) {
    return true;
  }
  if (isShellRoute(path)) return true;
  return false;
}



export function resolveSafeRedirect(

  target: string | null | undefined,

  context: RedirectContext,

  fallback: string,

): RedirectResolution {

  if (!target || target.trim() === '') {

    return { ok: true, path: fallback };

  }



  if (isJavascriptUrl(target)) {

    return { ok: false, reason: 'javascript' };

  }



  if (isExternalUrl(target)) {

    return { ok: false, reason: 'external' };

  }



  const path = normalizePath(target);



  if (matchesLevel8Blocked(path)) {
    return { ok: false, reason: 'level4_blocked' };
  }

  if (isLevel7Permitted(path) || isAppLedgerPath(path)) {
    if (!context.hasSession) {
      return { ok: false, reason: 'session_required' };
    }
    if (!context.hasTenant) {
      return { ok: false, reason: 'tenant_required' };
    }
    if (path === '/claims' || path.startsWith('/claims/')) {
      return { ok: true, path: path.replace(/^\/claims/, '/app/claims') };
    }
    if (path === '/trust' || path.startsWith('/trust/')) {
      return { ok: true, path: path.replace(/^\/trust/, '/app/trust') };
    }
    if (path === '/channels' || path.startsWith('/channels/')) {
      return { ok: true, path: path.replace(/^\/channels/, '/app/channels') };
    }
    if (path === '/budget' || path.startsWith('/budget/')) {
      return { ok: true, path: path.replace(/^\/budget/, '/app/budget') };
    }
    if (path === '/exceptions' || path.startsWith('/exceptions/')) {
      return { ok: true, path: path.replace(/^\/exceptions/, '/app/exceptions') };
    }
    return { ok: true, path };
  }

  if (matchesLevel6Blocked(path)) {
    return { ok: false, reason: 'level4_blocked' };
  }

  if (isLevel5Permitted(path) || isAppOperationalAuditPath(path)) {
    if (!context.hasSession) {
      return { ok: false, reason: 'session_required' };
    }
    if (!context.hasTenant) {
      return { ok: false, reason: 'tenant_required' };
    }
    if (path === '/audit' || path.startsWith('/audit/')) {
      return { ok: true, path: path.replace(/^\/audit/, '/app/audit') };
    }
    if (path === '/diagnostics' || path.startsWith('/diagnostics/')) {
      return { ok: true, path: path.replace(/^\/diagnostics/, '/app/diagnostics') };
    }
    return { ok: true, path };
  }

  if (isLevel4Permitted(path) || isAppGovernancePath(path) || isLevel11Permitted(path) || isAppBillingPath(path)) {
    if (!context.hasSession) {
      return { ok: false, reason: 'session_required' };
    }
    if (!context.hasTenant) {
      return { ok: false, reason: 'tenant_required' };
    }
    if (path === '/settings/team' || path.startsWith('/settings/team/')) {
      return { ok: true, path: path.replace(/^\/settings/, '/app/settings') };
    }
    if (path === '/settings/policy' || path.startsWith('/settings/policy/')) {
      return { ok: true, path: path.replace(/^\/settings/, '/app/settings') };
    }
    if (path === '/settings/billing' || path.startsWith('/settings/billing/')) {
      return { ok: true, path: path.replace(/^\/settings/, '/app/settings') };
    }
    return { ok: true, path };
  }

  if (isLevel3Permitted(path) || isAppActivationPath(path)) {
    if (!context.hasSession) {
      return { ok: false, reason: 'session_required' };
    }
    if (!context.hasTenant) {
      return { ok: false, reason: 'tenant_required' };
    }
    if (path === '/onboarding' || path.startsWith('/onboarding/')) {
      return { ok: true, path: path.replace(/^\/onboarding/, '/app/onboarding') };
    }
    if (path === '/integrations' || path.startsWith('/integrations/')) {
      return { ok: true, path: path.replace(/^\/integrations/, '/app/integrations') };
    }
    return { ok: true, path };
  }

  if (path.startsWith('/onboarding')) {
    return { ok: false, reason: 'onboarding_premature' };
  }



  if (isShellRoute(path)) {

    if (!context.hasSession) {

      return { ok: false, reason: 'session_required' };

    }

    if (!context.hasTenant) {

      return { ok: false, reason: 'tenant_required' };

    }

    return { ok: true, path: path.startsWith('/shell') ? path.replace(/^\/shell/, '/app') : path };

  }



  if (!isKnownPermitted(path)) {

    return { ok: false, reason: 'unknown' };

  }



  if (path.startsWith('/entry/workspace-created') && !context.hasTenant) {

    return { ok: false, reason: 'tenant_required' };

  }



  if (path.startsWith('/entry/session-ready') && !context.hasSession) {

    return { ok: false, reason: 'session_required' };

  }



  return { ok: true, path };

}



export function defaultPostLoginPath(): string {

  return '/entry/session-ready';

}



export function defaultPostSignupPath(): string {

  return '/app';

}



export function defaultShellPath(): string {

  return '/app';

}


