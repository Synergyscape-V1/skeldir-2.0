import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { AuthClient } from '../../../auth/authClient';
import { createMockUserProfile, getDefaultAuthClient } from '../../../auth/authClient';
import type { AuthEntrySurface, IdentityMode, InviteContext } from '../../../auth/identityFlow';
import {
  defaultPostLoginPath,
  defaultPostSignupPath,
  resolveSafeRedirect,
} from '../../../auth/redirectGuard';
import { establishSession, establishTenant, getAuthState } from '../../../auth/sessionStore';
import { profileFromLoginCredentials, profileFromSignUpInput } from '../../../auth/userProfile';
import type { OAuthProvider } from '../../../auth/types';
import { AuthEntryCanvas } from '../AuthEntryCanvas/AuthEntryCanvas';
import { CreateOrganizationModal } from '../CreateOrganizationModal/CreateOrganizationModal';
import { NotAMemberPanel } from '../NotAMemberPanel/NotAMemberPanel';
import { UnifiedIdentityModal } from '../UnifiedIdentityModal/UnifiedIdentityModal';

function parseInviteEmails(raw: string): string[] | undefined {
  const emails = raw
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
  return emails.length ? emails : undefined;
}

function resolveInitialSurface(): AuthEntrySurface {
  const { session, tenant } = getAuthState();
  if (session && !tenant) return 'create-organization';
  return 'identity';
}

export interface AuthEntryFlowProps {
  defaultIdentityMode?: IdentityMode;
  inviteContext?: InviteContext;
  redirectTarget?: string | null;
  authClient?: AuthClient;
  onNavigate?: (path: string) => void;
  dataRoute?: string;
}

export function AuthEntryFlow({
  defaultIdentityMode = 'sign-in',
  inviteContext,
  redirectTarget,
  authClient = getDefaultAuthClient(),
  onNavigate,
  dataRoute,
}: AuthEntryFlowProps) {
  const navigate = useNavigate();
  const [surface, setSurface] = useState<AuthEntrySurface>(resolveInitialSurface);
  const [submitting, setSubmitting] = useState(false);
  const [oauthPending, setOauthPending] = useState(false);
  const submitLock = useRef(false);

  const goToPath = useCallback(
    (path: string) => {
      if (onNavigate) onNavigate(path);
      else navigate(path, { replace: true });
    },
    [navigate, onNavigate],
  );

  const completeDashboard = useCallback(
    (hasTenant: boolean) => {
      const fallback = hasTenant ? defaultPostSignupPath() : defaultPostLoginPath();
      const resolution = resolveSafeRedirect(redirectTarget, { hasSession: true, hasTenant }, fallback);
      if (!resolution.ok) return;
      goToPath(resolution.path);
    },
    [goToPath, redirectTarget],
  );

  useEffect(() => {
    const { session, tenant } = getAuthState();
    if (!session || !tenant) return;

    const resolution = resolveSafeRedirect(
      redirectTarget,
      { hasSession: true, hasTenant: true },
      defaultPostSignupPath(),
    );
    if (resolution.ok) goToPath(resolution.path);
  }, [goToPath, redirectTarget]);

  const handleIdentitySuccess = useCallback(
    (hasTenant: boolean) => {
      if (inviteContext || hasTenant) {
        completeDashboard(hasTenant);
        return;
      }
      setSurface('create-organization');
    },
    [completeDashboard, inviteContext],
  );

  const runIdentity = async (runner: () => Promise<void>) => {
    if (submitLock.current || submitting || oauthPending) return;
    submitLock.current = true;
    setSubmitting(true);
    try {
      await runner();
    } finally {
      setSubmitting(false);
      submitLock.current = false;
    }
  };

  const handleSignIn = (values: { email: string; password: string }) => {
    void runIdentity(async () => {
      const outcome = await authClient.login(values);
      const profile = profileFromLoginCredentials(values);
      if (outcome.kind === 'success_session_established') {
        establishSession(outcome.session, null, profile);
        handleIdentitySuccess(Boolean(outcome.session.tenantId));
        return;
      }
      if (outcome.kind === 'success_tenant_created') {
        establishTenant(outcome.session, outcome.tenant, profile);
        completeDashboard(true);
      }
    });
  };

  const handleSignUp = (values: {
    firstName: string;
    lastName: string;
    email: string;
    password: string;
  }) => {
    void runIdentity(async () => {
      const profile = profileFromSignUpInput(values);
      const outcome = await authClient.signUpIdentity({
        firstName: values.firstName,
        lastName: values.lastName,
        email: values.email,
        password: values.password,
      });
      if (outcome.kind === 'success_session_established') {
        establishSession(outcome.session, null, profile);
        handleIdentitySuccess(Boolean(outcome.session.tenantId));
        return;
      }
      if (outcome.kind === 'success_tenant_created') {
        establishTenant(outcome.session, outcome.tenant, profile);
        completeDashboard(true);
      }
    });
  };

  const runOAuth = (provider: OAuthProvider) => {
    if (submitting || oauthPending) return;
    setOauthPending(true);
    void (async () => {
      try {
        const outcome = await authClient.startOAuth(provider);
        if (outcome.kind === 'success_session_established') {
          establishSession(outcome.session, null, createMockUserProfile());
          handleIdentitySuccess(Boolean(outcome.session.tenantId));
          return;
        }
        if (outcome.kind === 'success_tenant_created') {
          establishTenant(outcome.session, outcome.tenant, createMockUserProfile());
          completeDashboard(true);
        }
      } finally {
        setOauthPending(false);
      }
    })();
  };

  const handleCreateOrganization = (values: { organizationName: string; inviteTeammates: string }) => {
    void runIdentity(async () => {
      const outcome = await authClient.createOrganization({
        organizationName: values.organizationName,
        inviteEmails: parseInviteEmails(values.inviteTeammates),
      });
      if (outcome.kind === 'success_tenant_created') {
        establishTenant(outcome.session, outcome.tenant);
        completeDashboard(true);
      }
    });
  };

  return (
    <AuthEntryCanvas dataRoute={dataRoute}>
      {surface === 'identity' ? (
        <UnifiedIdentityModal
          defaultMode={defaultIdentityMode}
          inviteContext={inviteContext}
          submitting={submitting}
          oauthPending={oauthPending}
          onSignIn={handleSignIn}
          onSignUp={handleSignUp}
          onGoogleOAuth={() => runOAuth('google')}
        />
      ) : null}

      {surface === 'create-organization' ? (
        <CreateOrganizationModal
          submitting={submitting}
          onSubmit={handleCreateOrganization}
          onJoinExisting={() => setSurface('not-a-member')}
        />
      ) : null}

      {surface === 'not-a-member' ? (
        <NotAMemberPanel
          onCreateOrganization={() => setSurface('create-organization')}
          onCheckEmail={() => setSurface('identity')}
        />
      ) : null}
    </AuthEntryCanvas>
  );
}
