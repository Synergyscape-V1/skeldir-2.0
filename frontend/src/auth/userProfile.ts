import { DESIGN_SPRINT_EMAIL, getDesignSprintUserProfile, isDesignSprintAuthEnabled } from './designSprintAuth';
import type { ProductAuthState } from './sessionStore';
import type { IdentitySignUpInput, LoginCredentials, UserProfile } from './types';
export function deriveUserInitials(firstName: string, lastName: string): string {
  const first = firstName.trim();
  const last = lastName.trim();
  if (first && last) {
    return `${first[0] ?? ''}${last[0] ?? ''}`.toUpperCase();
  }
  if (first.length >= 2) {
    return first.slice(0, 2).toUpperCase();
  }
  if (first) {
    return first[0]!.toUpperCase();
  }
  return '?';
}

export function profileFromLoginCredentials(credentials: LoginCredentials): UserProfile {
  if (credentials.email === DESIGN_SPRINT_EMAIL) {
    return {
      firstName: 'Engineering',
      lastName: 'Skeldir',
      email: credentials.email,
    };
  }

  const localPart = credentials.email.split('@')[0] ?? 'User';
  const [firstSegment = localPart, secondSegment = ''] = localPart.split(/[._-]/);
  const firstName = firstSegment
    ? `${firstSegment[0]!.toUpperCase()}${firstSegment.slice(1)}`
    : 'User';

  return {
    firstName,
    lastName: secondSegment
      ? `${secondSegment[0]!.toUpperCase()}${secondSegment.slice(1)}`
      : '',
    email: credentials.email,
  };
}

export function profileFromSignUpInput(input: IdentitySignUpInput): UserProfile {
  return {
    firstName: input.firstName.trim(),
    lastName: input.lastName.trim(),
    email: input.email.trim(),
  };
}

/** Display identity for sidebar account — backfills design-sprint profile when session exists without user. */
export function resolveSidebarAccountUser(state: ProductAuthState): UserProfile | null {
  if (state.user) return state.user;
  if (!state.session || !state.tenant) return null;
  if (isDesignSprintAuthEnabled()) return getDesignSprintUserProfile();
  return null;
}
