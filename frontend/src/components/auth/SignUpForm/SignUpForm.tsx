import type { AuthClient } from '../../../auth/authClient';
import { getDefaultAuthClient } from '../../../auth/authClient';
import type { IdentityMode } from '../../../auth/identityFlow';
import { useSearchParams } from 'react-router-dom';
import { AuthEntryFlow } from '../AuthEntryFlow/AuthEntryFlow';

export interface SignUpFormProps {
  authClient?: AuthClient;
  redirectTarget?: string | null;
  onNavigate?: (path: string) => void;
}

/**
 * Harness-compatible wrapper around the unified identity sign-up surface.
 * Organization creation is a separate modal step in AuthEntryFlow.
 */
export function SignUpForm({
  authClient = getDefaultAuthClient(),
  redirectTarget,
  onNavigate,
}: SignUpFormProps) {
  const [searchParams] = useSearchParams();
  const redirectParam = redirectTarget ?? searchParams.get('redirect');

  return (
    <AuthEntryFlow
      defaultIdentityMode={'sign-up' satisfies IdentityMode}
      authClient={authClient}
      redirectTarget={redirectParam}
      onNavigate={onNavigate}
      dataRoute="/signup-form"
    />
  );
}
