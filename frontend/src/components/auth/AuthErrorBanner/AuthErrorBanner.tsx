import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { AUTH_COPY } from '../../../auth/copy';

export interface AuthErrorBannerProps {
  message: string;
  detail?: string;
  variant?: 'error' | 'warning' | 'info';
}

export function AuthErrorBanner({ message, detail, variant = 'error' }: AuthErrorBannerProps) {
  return <ErrorBanner variant={variant === 'info' ? 'info' : variant} message={message} detail={detail} />;
}

export function UnsafeRedirectBanner() {
  return <AuthErrorBanner message={AUTH_COPY.unsafeRedirect} />;
}

export function AlreadyAuthenticatedBanner() {
  return <AuthErrorBanner message={AUTH_COPY.alreadyAuthenticated} variant="info" />;
}
