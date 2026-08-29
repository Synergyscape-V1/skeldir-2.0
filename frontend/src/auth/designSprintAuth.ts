import type { Session, Tenant, UserProfile } from './types';

/** Dev-only design sprint credentials — stripped from production builds via import.meta.env.DEV. */
export const DESIGN_SPRINT_EMAIL = 'engineering@skeldir.com';
export const DESIGN_SPRINT_PASSWORD = 'AliAli223!';

const STORAGE_KEY = 'skeldir.design-sprint.auth';

export function isDesignSprintAuthEnabled(): boolean {
  return Boolean(import.meta.env.DEV && import.meta.env.MODE !== 'test');
}

export function getDesignSprintFieldDefaults(): {
  email: string;
  password: string;
  confirmPassword: string;
} {
  if (!isDesignSprintAuthEnabled()) {
    return { email: '', password: '', confirmPassword: '' };
  }
  return {
    email: DESIGN_SPRINT_EMAIL,
    password: DESIGN_SPRINT_PASSWORD,
    confirmPassword: DESIGN_SPRINT_PASSWORD,
  };
}

export function getDesignSprintUserProfile(): UserProfile {
  return {
    firstName: 'Engineering',
    lastName: 'Skeldir',
    email: DESIGN_SPRINT_EMAIL,
  };
}

export interface PersistedDesignSprintAuth {
  session: Session;
  tenant: Tenant | null;
  user: UserProfile | null;
}

export function persistDesignSprintAuth(
  session: Session,
  tenant: Tenant | null,
  user: UserProfile | null,
): void {
  if (!isDesignSprintAuthEnabled() || typeof localStorage === 'undefined') return;
  const payload: PersistedDesignSprintAuth = { session, tenant, user };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function readPersistedDesignSprintAuth(): PersistedDesignSprintAuth | null {
  if (!isDesignSprintAuthEnabled() || typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedDesignSprintAuth;
    if (!parsed?.session?.sessionId) return null;
    if (!parsed.user && isDesignSprintAuthEnabled()) {
      parsed.user = getDesignSprintUserProfile();
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearPersistedDesignSprintAuth(): void {
  if (!isDesignSprintAuthEnabled() || typeof localStorage === 'undefined') return;
  localStorage.removeItem(STORAGE_KEY);
}
