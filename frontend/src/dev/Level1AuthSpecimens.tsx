import { useSearchParams } from 'react-router-dom';
import { AUTH_COPY } from '../auth/copy';
import { getAuthState } from '../auth/sessionStore';
import { AuthEntryFlow } from '../components/auth/AuthEntryFlow/AuthEntryFlow';
import { CreateOrganizationModal } from '../components/auth/CreateOrganizationModal/CreateOrganizationModal';
import { NotAMemberPanel } from '../components/auth/NotAMemberPanel/NotAMemberPanel';
import { UnifiedIdentityModal } from '../components/auth/UnifiedIdentityModal/UnifiedIdentityModal';
import { GoogleOAuthButton } from '../components/auth/OAuthButtons/OAuthButtons';
import { AuthErrorBanner } from '../components/auth/AuthErrorBanner/AuthErrorBanner';
import { BusinessEmailInput } from '../components/auth/BusinessEmailInput/BusinessEmailInput';
import { Card } from '../components/layout/Card/Card';
import { PageSurface } from '../components/layout/PageSurface/PageSurface';
import { Typography } from '../components/layout/Typography/Typography';
import styles from '../app/authPages.module.css';

export function Level1AuthSpecimens() {
  const [searchParams] = useSearchParams();
  const fixture = searchParams.get('fixture') ?? 'gallery';

  return (
    <PageSurface>
      <div className={styles.page} data-specimen-root="level1-auth">
        <div className={styles.cardWrap} style={{ maxWidth: 960 }}>
          <Typography variant="h1">Level 1 Auth Specimens</Typography>
          <div style={{ display: 'grid', gap: 'var(--sk-space-6)', marginTop: 'var(--sk-space-6)' }}>
            {fixture === 'gallery' || fixture === 'unified-identity' ? (
              <section data-specimen="unified-identity-modal" aria-label="Unified identity modal (single component, toggle states)">
                <Typography variant="h3">Single modal — use top segmented selector to expand/contract</Typography>
                <UnifiedIdentityModal
                  onSignIn={() => undefined}
                  onSignUp={() => undefined}
                  onGoogleOAuth={() => undefined}
                />
              </section>
            ) : null}
            {fixture === 'gallery' || fixture === 'unified-invited' ? (
              <section data-specimen="unified-invited" aria-label="Invited unified identity">
                <UnifiedIdentityModal
                  inviteContext={{ organizationName: 'Acme RevOps' }}
                  onSignIn={() => undefined}
                  onSignUp={() => undefined}
                  onGoogleOAuth={() => undefined}
                />
              </section>
            ) : null}
            {fixture === 'gallery' || fixture === 'create-organization' ? (
              <section data-specimen="create-organization" aria-label="Post-identity create organization surface">
                <CreateOrganizationModal onSubmit={() => undefined} onJoinExisting={() => undefined} />
              </section>
            ) : null}
            {fixture === 'gallery' || fixture === 'not-a-member' ? (
              <section data-specimen="not-a-member" aria-label="Not a member panel">
                <NotAMemberPanel onCreateOrganization={() => undefined} onCheckEmail={() => undefined} />
              </section>
            ) : null}
            {fixture === 'gallery' || fixture === 'auth-entry-flow' ? (
              <section data-specimen="auth-entry-flow" aria-label="Full auth entry flow">
                <AuthEntryFlow dataRoute="/dev/auth-specimens" />
              </section>
            ) : null}
            {fixture === 'gallery' || fixture === 'oauth-google' ? (
              <section data-specimen="oauth-google" aria-label="Google OAuth button">
                <GoogleOAuthButton onClick={() => undefined} />
              </section>
            ) : null}
            {fixture === 'gallery' || fixture === 'business-email' ? (
              <section data-specimen="business-email-input-states" aria-label="Business email input states">
                <BusinessEmailInput value="ops@acme.com" onChange={() => undefined} />
                <BusinessEmailInput value="" onChange={() => undefined} showValidation />
              </section>
            ) : null}
            {fixture === 'gallery' || fixture === 'auth-error-delegated' ? (
              <section data-specimen="auth-error-delegated" aria-label="Delegated auth error surface">
                <AuthErrorBanner message={AUTH_COPY.invalidCredentials} />
              </section>
            ) : null}
            {fixture === 'gallery' || fixture === 'already-authenticated' ? (
              <section data-specimen="already-authenticated" aria-label="Already authenticated info">
                <Card title={AUTH_COPY.handoffSessionTitle}>
                  <p className={styles.handoffBody}>{AUTH_COPY.alreadyAuthenticated}</p>
                  <p className={styles.meta}>Session: {getAuthState().session?.sessionId ?? 'none'}</p>
                </Card>
              </section>
            ) : null}
          </div>
        </div>
      </div>
    </PageSurface>
  );
}
