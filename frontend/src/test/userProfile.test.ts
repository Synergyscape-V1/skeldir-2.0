import { deriveUserInitials, profileFromLoginCredentials, profileFromSignUpInput, resolveSidebarAccountUser } from '../auth/userProfile';
import { describe, expect, it, vi } from 'vitest';

describe('userProfile', () => {
  it('derives initials from first and last name', () => {
    expect(deriveUserInitials('Alex', 'Operator')).toBe('AO');
    expect(deriveUserInitials('Engineering', 'Skeldir')).toBe('ES');
  });

  it('builds profile from sign-up input', () => {
    expect(
      profileFromSignUpInput({
        firstName: 'Alex',
        lastName: 'Operator',
        email: 'alex@acme.com',
        password: 'secret',
      }),
    ).toEqual({
      firstName: 'Alex',
      lastName: 'Operator',
      email: 'alex@acme.com',
    });
  });

  it('builds design sprint profile from login credentials', () => {
    expect(
      profileFromLoginCredentials({
        email: 'engineering@skeldir.com',
        password: 'AliAli223!',
      }),
    ).toEqual({
      firstName: 'Engineering',
      lastName: 'Skeldir',
      email: 'engineering@skeldir.com',
    });
  });

  it('resolves sidebar account user from design sprint session without stored profile', () => {
    vi.stubEnv('MODE', 'development');
    expect(
      resolveSidebarAccountUser({
        session: { sessionId: 's1', userId: 'u1', expiresAt: '2099-01-01T00:00:00.000Z' },
        tenant: { tenantId: 't1', workspaceName: 'Acme', onboardingStatus: 'ready' },
        user: null,
        bootstrapStatus: 'ready',
      }),
    ).toEqual({
      firstName: 'Engineering',
      lastName: 'Skeldir',
      email: 'engineering@skeldir.com',
    });
    vi.unstubAllEnvs();
  });
});
