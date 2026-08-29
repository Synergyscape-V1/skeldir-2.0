import type { AuthClient } from '../../../auth/authClient';
import { getDefaultAuthClient } from '../../../auth/authClient';
import type { IdentityMode } from '../../../auth/identityFlow';
import { useSearchParams } from 'react-router-dom';
import { AuthEntryFlow } from '../AuthEntryFlow/AuthEntryFlow';

export interface LoginFormProps {
  authClient?: AuthClient;
  redirectTarget?: string | null;
  sessionExpired?: boolean;
  alreadyAuthenticated?: boolean;
  onNavigate?: (path: string) => void;
}

/**
 * Harness-compatible wrapper around the unified identity sign-in surface.
 * Auth error handling is delegated to the authentication team.
 */
export function LoginForm({
  authClient = getDefaultAuthClient(),
  redirectTarget,
  onNavigate,
}: LoginFormProps) {
  const [searchParams] = useSearchParams();
  const redirectParam = redirectTarget ?? searchParams.get('redirect');

  return (
    <AuthEntryFlow
      defaultIdentityMode={'sign-in' satisfies IdentityMode}
      authClient={authClient}
      redirectTarget={redirectParam}
      onNavigate={onNavigate}
      dataRoute="/login-form"
    />
  );
}
