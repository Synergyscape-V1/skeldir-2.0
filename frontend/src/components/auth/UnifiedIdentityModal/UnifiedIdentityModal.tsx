import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { IdentityMode, InviteContext } from '../../../auth/identityFlow';
import { AUTH_COPY } from '../../../auth/copy';
import { getDesignSprintFieldDefaults } from '../../../auth/designSprintAuth';
import { FormField } from '../../form/FormField/FormField';
import { SubmitButton } from '../../form/SubmitButton/SubmitButton';
import { GoogleOAuthButton } from '../OAuthButtons/OAuthButtons';
import { IdentityModeSelector } from './IdentityModeSelector';
import styles from './UnifiedIdentityModal.module.css';

export interface UnifiedIdentityModalProps {
  /** Initial toggle state on first mount only — toggling is always in-place within this modal. */
  defaultMode?: IdentityMode;
  inviteContext?: InviteContext;
  submitting?: boolean;
  oauthPending?: boolean;
  onModeChange?: (mode: IdentityMode) => void;
  onSignIn: (values: { email: string; password: string }) => void;
  onSignUp: (values: {
    firstName: string;
    lastName: string;
    email: string;
    password: string;
    confirmPassword: string;
  }) => void;
  onGoogleOAuth: () => void;
}

export function UnifiedIdentityModal({
  defaultMode = 'sign-in',
  inviteContext,
  submitting = false,
  oauthPending = false,
  onModeChange,
  onSignIn,
  onSignUp,
  onGoogleOAuth,
}: UnifiedIdentityModalProps) {
  const dialogTitleId = useId();
  const sprintDefaults = getDesignSprintFieldDefaults();
  const [mode, setMode] = useState<IdentityMode>(defaultMode);
  const [email, setEmail] = useState(sprintDefaults.email);
  const [password, setPassword] = useState(sprintDefaults.password);
  const [confirmPassword, setConfirmPassword] = useState(sprintDefaults.confirmPassword);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [showValidation, setShowValidation] = useState(false);
  const liveRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMode(defaultMode);
  }, [defaultMode]);

  const announce = useCallback((message: string) => {
    if (liveRef.current) liveRef.current.textContent = message;
  }, []);

  const isSignUp = mode === 'sign-up';
  const busy = submitting || oauthPending;

  const setIdentityMode = useCallback(
    (next: IdentityMode) => {
      setShowValidation(false);
      setMode(next);
      onModeChange?.(next);
    },
    [onModeChange],
  );

  const emailError = showValidation && !email.trim() ? 'Enter your email.' : undefined;
  const passwordError = showValidation && !password ? 'Enter your password.' : undefined;
  const firstNameError =
    showValidation && isSignUp && !firstName.trim() ? AUTH_COPY.firstNameRequired : undefined;
  const lastNameError =
    showValidation && isSignUp && !lastName.trim() ? AUTH_COPY.lastNameRequired : undefined;
  const confirmPasswordError =
    showValidation && isSignUp && !confirmPassword
      ? AUTH_COPY.confirmPasswordRequired
      : showValidation && isSignUp && confirmPassword && confirmPassword !== password
        ? AUTH_COPY.passwordMismatch
        : undefined;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setShowValidation(true);

    if (!email.trim() || !password) {
      announce('Fix the highlighted fields.');
      return;
    }

    if (isSignUp) {
      if (!firstName.trim() || !lastName.trim() || !confirmPassword || confirmPassword !== password) {
        announce('Fix the highlighted fields.');
        return;
      }
      onSignUp({
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim(),
        password,
        confirmPassword,
      });
      return;
    }

    onSignIn({ email: email.trim(), password });
  };

  return (
    <form
      className={styles.modal}
      data-unified-identity-modal
      data-identity-mode={mode}
      role="dialog"
      aria-modal="true"
      aria-labelledby={dialogTitleId}
      noValidate
      onSubmit={handleSubmit}
    >
      <div ref={liveRef} className={styles.statusLive} aria-live="polite" />
      <header className={styles.header}>
        <h1 id={dialogTitleId} className={styles.title}>
          {AUTH_COPY.identityWelcomeTitle}
        </h1>
        <p className={styles.subtitle}>{AUTH_COPY.identityWelcomeSubtitle}</p>
        {inviteContext ? (
          <p className={styles.framing}>{AUTH_COPY.identityInviteFraming(inviteContext.organizationName)}</p>
        ) : null}
      </header>

      <IdentityModeSelector mode={mode} disabled={busy} onChange={setIdentityMode} />

      <div className={styles.expandRegion} data-expanded={isSignUp} data-identity-name-region>
        <div className={styles.expandInner} aria-hidden={!isSignUp}>
          <div className={styles.nameRow}>
            <FormField
              id="identity-first-name"
              label={AUTH_COPY.firstNameLabel}
              autoComplete="given-name"
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
              disabled={busy || !isSignUp}
              error={firstNameError}
            />
            <FormField
              id="identity-last-name"
              label={AUTH_COPY.lastNameLabel}
              autoComplete="family-name"
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
              disabled={busy || !isSignUp}
              error={lastNameError}
            />
          </div>
        </div>
      </div>

      <div className={styles.coreFields}>
        <FormField
          id="identity-email"
          label={AUTH_COPY.emailLabel}
          type="email"
          autoComplete={isSignUp ? 'email' : 'username'}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={busy}
          error={emailError}
        />
        <FormField
          id="identity-password"
          label={AUTH_COPY.passwordLabel}
          type="password"
          autoComplete={isSignUp ? 'new-password' : 'current-password'}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={busy}
          error={passwordError}
        />
      </div>

      <div className={styles.expandRegion} data-expanded={isSignUp} data-identity-signup-extras>
        <div className={styles.expandInner}>
          <div className={styles.signUpExtras} aria-hidden={!isSignUp}>
            <FormField
              id="identity-confirm-password"
              label={AUTH_COPY.confirmPasswordLabel}
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              disabled={busy || !isSignUp}
              error={confirmPasswordError}
            />
            <p className={styles.divider} aria-hidden="true">
              {AUTH_COPY.oauthDivider}
            </p>
            <GoogleOAuthButton
              onClick={onGoogleOAuth}
              loading={oauthPending}
              pendingProvider={oauthPending ? 'google' : null}
              disabled={submitting || !isSignUp}
            />
          </div>
        </div>
      </div>

      <SubmitButton loading={submitting} loadingLabel={AUTH_COPY.submitting} disabled={oauthPending}>
        {isSignUp ? AUTH_COPY.submitSignup : AUTH_COPY.submitLogin}
      </SubmitButton>
    </form>
  );
}
