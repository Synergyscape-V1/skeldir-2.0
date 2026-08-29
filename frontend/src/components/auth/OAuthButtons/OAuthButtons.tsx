import type { OAuthProvider } from '../../../auth/types';
import { AUTH_COPY } from '../../../auth/copy';
import { SubmitButton } from '../../form/SubmitButton/SubmitButton';

const PROVIDER_LABELS: Record<OAuthProvider, string> = {
  github: 'GitHub',
  google: 'Google',
  microsoft: 'Microsoft',
};

export interface OAuthButtonProps {
  provider: OAuthProvider;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  pendingProvider?: OAuthProvider | null;
}

function OAuthButtonBase({
  provider,
  onClick,
  disabled,
  loading,
  pendingProvider,
}: OAuthButtonProps) {
  const label = PROVIDER_LABELS[provider];
  const isPending = loading && pendingProvider === provider;
  const isDisabled = disabled || loading;

  return (
    <SubmitButton
      type="button"
      variant="oauth"
      onClick={onClick}
      disabled={isDisabled}
      loading={isPending}
      loadingLabel={AUTH_COPY.oauthPending(label)}
      aria-label={`Continue with ${label}`}
    >
      Continue with {label}
    </SubmitButton>
  );
}

export function GitHubOAuthButton(props: Omit<OAuthButtonProps, 'provider'>) {
  return <OAuthButtonBase provider="github" {...props} />;
}

export function GoogleOAuthButton(props: Omit<OAuthButtonProps, 'provider'>) {
  return <OAuthButtonBase provider="google" {...props} />;
}

export function MicrosoftOAuthButton(props: Omit<OAuthButtonProps, 'provider'>) {
  return <OAuthButtonBase provider="microsoft" {...props} />;
}

export { OAuthButtonBase };
