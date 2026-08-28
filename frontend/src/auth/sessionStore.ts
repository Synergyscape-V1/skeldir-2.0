import type { Session, Tenant, UserProfile } from './types';
import {
  clearPersistedDesignSprintAuth,
  getDesignSprintUserProfile,
  isDesignSprintAuthEnabled,
  persistDesignSprintAuth,
} from './designSprintAuth';

export interface ProductAuthState {
  session: Session | null;
  tenant: Tenant | null;
  user: UserProfile | null;
  bootstrapStatus: 'unknown' | 'loading' | 'ready';
}

let state: ProductAuthState = {
  session: null,
  tenant: null,
  user: null,
  bootstrapStatus: 'unknown',
};

const listeners = new Set<(next: ProductAuthState) => void>();

export function getAuthState(): ProductAuthState {
  return state;
}

export function subscribeAuthState(listener: (next: ProductAuthState) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function emit(next: ProductAuthState): void {
  state = next;
  for (const listener of listeners) listener(next);
}

export function setBootstrapLoading(): void {
  emit({ ...state, bootstrapStatus: 'loading' });
}

export function setBootstrapReady(): void {
  emit({ ...state, bootstrapStatus: 'ready' });
}

function resolveStoredUser(
  user: UserProfile | null | undefined,
  tenant: Tenant | null,
): UserProfile | null {
  if (user !== undefined) {
    if (user) return user;
    if (tenant && isDesignSprintAuthEnabled()) return getDesignSprintUserProfile();
    return null;
  }
  if (state.user) return state.user;
  if (tenant && isDesignSprintAuthEnabled()) return getDesignSprintUserProfile();
  return null;
}

export function establishSession(
  session: Session,
  tenant?: Tenant | null,
  user?: UserProfile | null,
): void {
  const resolvedTenant = tenant ?? state.tenant;
  const next = {
    session,
    tenant: resolvedTenant,
    user: resolveStoredUser(user, resolvedTenant),
    bootstrapStatus: 'ready' as const,
  };
  emit(next);
  persistDesignSprintAuth(next.session, next.tenant, next.user);
}

export function establishTenant(session: Session, tenant: Tenant, user?: UserProfile | null): void {
  const next = {
    session,
    tenant,
    user: resolveStoredUser(user, tenant),
    bootstrapStatus: 'ready' as const,
  };
  emit(next);
  persistDesignSprintAuth(session, tenant, next.user);
}

export function clearSession(): void {
  emit({ session: null, tenant: null, user: null, bootstrapStatus: 'ready' });
  clearPersistedDesignSprintAuth();
}

/** Test-only reset */
export function resetAuthStateForTests(): void {
  emit({ session: null, tenant: null, user: null, bootstrapStatus: 'unknown' });
}
