import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createAuthClient,
  createMockAuthTransport,
  createMockSession,
  createMockTenant,
  resetDefaultAuthClient,
  setDefaultAuthClient,
} from '../auth/authClient';
import { AUTH_COPY } from '../auth/copy';
import { mapAuthOutcomeToMessage } from '../auth/outcomeMapping';
import { resolveSafeRedirect } from '../auth/redirectGuard';
import { clearSession, establishSession, getAuthState, resetAuthStateForTests } from '../auth/sessionStore';
import {
  assertLevel1ComponentsExist,
  assertLevel1RoutesExist,
  runLevel1NegativeScopeScan,
} from '../audit/level1NegativeScopeScan';
import { runNegativeScopeScan } from '../audit/negativeScopeScan';
import { runTokenAudit } from '../audit/tokenAudit';
import { LoginForm } from '../components/auth/LoginForm/LoginForm';
import { SignUpForm } from '../components/auth/SignUpForm/SignUpForm';
import { BusinessEmailInput } from '../components/auth/BusinessEmailInput/BusinessEmailInput';
import { GoogleOAuthButton } from '../components/auth/OAuthButtons/OAuthButtons';
import { LoginPage } from '../app/routes/AuthRoutes';
import { AuthEntryFlow } from '../components/auth/AuthEntryFlow/AuthEntryFlow';

function renderLogin(override?: Parameters<typeof createMockAuthTransport>[0]) {
  const client = createAuthClient(createMockAuthTransport(override));
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginForm authClient={client} onNavigate={() => undefined} />} />
        <Route path="/entry/session-ready" element={<div>Session ready handoff</div>} />
        <Route path="/app" element={<div>Dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderSignup(override?: Parameters<typeof createMockAuthTransport>[0]) {
  const client = createAuthClient(createMockAuthTransport(override));
  return render(
    <MemoryRouter initialEntries={['/signup']}>
      <Routes>
        <Route path="/signup" element={<SignUpForm authClient={client} onNavigate={() => undefined} />} />
        <Route path="/entry/workspace-created" element={<div>Workspace handoff</div>} />
        <Route path="/app" element={<div>Dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Level 1 Harness — Scope and regression', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetDefaultAuthClient();
    clearSession();
  });

  it('Level 0 negative scope still passes on substrate', () => {
    expect(runNegativeScopeScan().violations).toEqual([]);
  });

  it('Level 1 negative scope passes', () => {
    expect(runLevel1NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 1 routes exist', () => {
    expect(assertLevel1RoutesExist()).toEqual({ ok: true, missing: [] });
  });

  it('Level 1 components exist', () => {
    expect(assertLevel1ComponentsExist()).toEqual({ ok: true, missing: [] });
  });

  it('token audit passes including auth surfaces', () => {
    expect(runTokenAudit().violations).toEqual([]);
  });
});

describe('Level 1 Harness — LoginForm', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    clearSession();
  });

  it('positive: successful login establishes session', async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText(AUTH_COPY.emailLabel), 'ops@acme.com');
    await user.type(screen.getByLabelText(AUTH_COPY.passwordLabel), 'password123');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitLogin }));
    await waitFor(() => {
      expect(getAuthState().session?.sessionId).toBe('sess_test_001');
    });
  });

  it('negative: invalid credentials do not establish session', async () => {
    const user = userEvent.setup();
    renderLogin({ loginResult: { kind: 'invalid_credentials' } });
    await user.type(screen.getByLabelText(AUTH_COPY.emailLabel), 'ops@acme.com');
    await user.type(screen.getByLabelText(AUTH_COPY.passwordLabel), 'wrong');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitLogin }));
    await waitFor(() => {
      expect(getAuthState().session).toBeNull();
    });
  });

  it('negative: unsafe redirect does not navigate externally', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(
      <MemoryRouter initialEntries={['/login?redirect=https%3A%2F%2Fevil.test']}>
        <Routes>
          <Route
            path="/login"
            element={
              <LoginForm
                authClient={createAuthClient(createMockAuthTransport())}
                onNavigate={onNavigate}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(AUTH_COPY.emailLabel), 'ops@acme.com');
    await user.type(screen.getByLabelText(AUTH_COPY.passwordLabel), 'password123');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitLogin }));
    await waitFor(() => expect(getAuthState().session?.sessionId).toBe('sess_test_001'));
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it('negative: double submit prevented while pending', async () => {
    const user = userEvent.setup();
    const transport = createMockAuthTransport({ delayMs: 100 });
    const login = vi.fn(transport.login.bind(transport));
    transport.login = login;
    const client = createAuthClient(transport);
    render(
      <MemoryRouter>
        <LoginForm authClient={client} onNavigate={() => undefined} />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(AUTH_COPY.emailLabel), 'ops@acme.com');
    await user.type(screen.getByLabelText(AUTH_COPY.passwordLabel), 'password123');
    const submit = screen.getByRole('button', { name: AUTH_COPY.submitLogin });
    await user.click(submit);
    await user.click(submit);
    await waitFor(() => expect(login).toHaveBeenCalledTimes(1));
  });
});

describe('Level 1 Harness — SignUpForm', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    clearSession();
  });

  it('positive: signup creates tenant state after organization step', async () => {
    const user = userEvent.setup();
    renderSignup();
    await user.type(screen.getByLabelText(AUTH_COPY.firstNameLabel), 'Alex');
    await user.type(screen.getByLabelText(AUTH_COPY.lastNameLabel), 'Operator');
    await user.type(screen.getByLabelText(AUTH_COPY.emailLabel), 'ops@acme.com');
    await user.type(screen.getByLabelText(AUTH_COPY.passwordLabel), 'password123');
    await user.type(screen.getByLabelText(AUTH_COPY.confirmPasswordLabel), 'password123');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitSignup }));
    await screen.findByText(AUTH_COPY.createOrganizationTitle);
    await user.type(screen.getByLabelText(AUTH_COPY.organizationNameLabel), 'Acme RevOps');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitCreateOrganization }));
    await waitFor(() => {
      expect(getAuthState().tenant?.tenantId).toBe('tenant_test_001');
    });
  });

  it('negative: tenant already exists does not create tenant', async () => {
    const user = userEvent.setup();
    renderSignup({ createOrganizationResult: { kind: 'tenant_already_exists' } });
    await user.type(screen.getByLabelText(AUTH_COPY.firstNameLabel), 'Alex');
    await user.type(screen.getByLabelText(AUTH_COPY.lastNameLabel), 'Operator');
    await user.type(screen.getByLabelText(AUTH_COPY.emailLabel), 'ops@acme.com');
    await user.type(screen.getByLabelText(AUTH_COPY.passwordLabel), 'password123');
    await user.type(screen.getByLabelText(AUTH_COPY.confirmPasswordLabel), 'password123');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitSignup }));
    await screen.findByText(AUTH_COPY.createOrganizationTitle);
    await user.type(screen.getByLabelText(AUTH_COPY.organizationNameLabel), 'Acme RevOps');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitCreateOrganization }));
    await waitFor(() => expect(getAuthState().tenant).toBeNull());
  });

  it('positive: signup can redirect to /app shell when tenant exists', () => {
    expect(resolveSafeRedirect('/app', { hasSession: true, hasTenant: true }, '/entry/workspace-created')).toEqual({
      ok: true,
      path: '/app',
    });
  });

  it('negative: signup cannot redirect to /app without tenant', () => {
    expect(resolveSafeRedirect('/app', { hasSession: true, hasTenant: false }, '/entry/workspace-created').ok).toBe(
      false,
    );
  });
});

describe('Level 1 Harness — Unified auth entry flow', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    clearSession();
  });

  it('sign-in/sign-up segmented selector expands the same modal in place without route change', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<AuthEntryFlow dataRoute="/login" />} />
        </Routes>
      </MemoryRouter>,
    );
    const modal = () => screen.getByRole('dialog');
    expect(modal()).toHaveAttribute('data-identity-mode', 'sign-in');
    expect(screen.getByRole('tab', { name: AUTH_COPY.submitLogin })).toHaveAttribute('aria-selected', 'true');
    await user.click(screen.getByRole('tab', { name: AUTH_COPY.submitSignup }));
    expect(modal()).toHaveAttribute('data-identity-mode', 'sign-up');
    expect(screen.getByRole('tab', { name: AUTH_COPY.submitSignup })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText(AUTH_COPY.firstNameLabel)).not.toBeDisabled();
    expect(screen.getByRole('button', { name: AUTH_COPY.continueWithGoogle })).toBeInTheDocument();
    expect(screen.queryByText(/Don't have an account/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: AUTH_COPY.submitLogin }));
    expect(modal()).toHaveAttribute('data-identity-mode', 'sign-in');
  });

  it('invited users see organization framing copy', () => {
    render(
      <MemoryRouter>
        <AuthEntryFlow inviteContext={{ organizationName: 'Acme RevOps' }} dataRoute="/auth" />
      </MemoryRouter>,
    );
    expect(screen.getByText(/invited to join Acme RevOps/i)).toBeInTheDocument();
  });

  it('join existing organization surfaces not-a-member panel', async () => {
    const user = userEvent.setup();
    const client = createAuthClient(createMockAuthTransport());
    render(
      <MemoryRouter>
        <AuthEntryFlow authClient={client} defaultIdentityMode="sign-up" dataRoute="/signup" />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(AUTH_COPY.firstNameLabel), 'Alex');
    await user.type(screen.getByLabelText(AUTH_COPY.lastNameLabel), 'Operator');
    await user.type(screen.getByLabelText(AUTH_COPY.emailLabel), 'ops@acme.com');
    await user.type(screen.getByLabelText(AUTH_COPY.passwordLabel), 'password123');
    await user.type(screen.getByLabelText(AUTH_COPY.confirmPasswordLabel), 'password123');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitSignup }));
    await screen.findByText(AUTH_COPY.createOrganizationTitle);
    await user.click(screen.getByRole('button', { name: AUTH_COPY.joinExistingOrganization }));
    expect(screen.getByText(AUTH_COPY.notAMemberBody)).toBeInTheDocument();
  });

  it('invited identity success bypasses organization modal', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const client = createAuthClient(
      createMockAuthTransport({
        signUpIdentityResult: {
          kind: 'success_session_established',
          session: createMockSession({ tenantId: 'tenant_invited' }),
        },
      }),
    );
    render(
      <MemoryRouter>
        <AuthEntryFlow
          authClient={client}
          defaultIdentityMode="sign-up"
          inviteContext={{ organizationName: 'Acme RevOps' }}
          onNavigate={onNavigate}
        />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(AUTH_COPY.firstNameLabel), 'Alex');
    await user.type(screen.getByLabelText(AUTH_COPY.lastNameLabel), 'Operator');
    await user.type(screen.getByLabelText(AUTH_COPY.emailLabel), 'ops@acme.com');
    await user.type(screen.getByLabelText(AUTH_COPY.passwordLabel), 'password123');
    await user.type(screen.getByLabelText(AUTH_COPY.confirmPasswordLabel), 'password123');
    await user.click(screen.getByRole('button', { name: AUTH_COPY.submitSignup }));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('/app'));
    expect(screen.queryByText(AUTH_COPY.createOrganizationTitle)).not.toBeInTheDocument();
  });
});

describe('Level 1 Harness — OAuth and accessibility', () => {
  it('OAuth buttons expose accessible provider names', () => {
    render(<GoogleOAuthButton onClick={() => undefined} />);
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeInTheDocument();
  });

  it('BusinessEmailInput associates field errors', async () => {
    const user = userEvent.setup();
    render(<BusinessEmailInput value="" onChange={() => undefined} showValidation />);
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your work email.');
    expect(screen.getByLabelText(AUTH_COPY.emailLabel)).toHaveAttribute('aria-invalid', 'true');
    await user.tab();
  });
});

describe('Level 1 Harness — App routes', () => {
  it('registers product-owned /login route page', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(AUTH_COPY.identityWelcomeTitle)).toBeInTheDocument();
    expect(screen.getByText(AUTH_COPY.identityWelcomeSubtitle)).toBeInTheDocument();
    expect(screen.getByLabelText('Skeldir')).toBeInTheDocument();
  });
});

describe('Level 1 Harness — Sabotage controls', () => {
  it('meta-negative: external redirect resolution fails closed', () => {
    expect(resolveSafeRedirect('https://evil.test', { hasSession: true, hasTenant: true }, '/entry/session-ready').ok).toBe(
      false,
    );
  });

  it('meta-negative: raw backend error must not be shown verbatim helper', () => {
    const message = mapAuthOutcomeToMessage({ kind: 'unknown_error', detail: 'SQL connection timeout secret' });
    expect(message).toBe(AUTH_COPY.unknownAuthState);
    expect(message).not.toContain('SQL');
  });

  it('meta-negative: billing route resolves with session and tenant', () => {
    expect(resolveSafeRedirect('/settings/billing', { hasSession: true, hasTenant: true }, '/entry/session-ready')).toEqual({
      ok: true,
      path: '/app/settings/billing',
    });
    expect(resolveSafeRedirect('/onboarding', { hasSession: true, hasTenant: true }, '/entry/session-ready')).toEqual({
      ok: true,
      path: '/app/onboarding',
    });
  });
});
