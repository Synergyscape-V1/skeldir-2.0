import { useCallback, useRef, useState } from 'react';
import { AUTH_COPY } from '../../../auth/copy';
import { FormField } from '../../form/FormField/FormField';
import { SubmitButton } from '../../form/SubmitButton/SubmitButton';
import sharedStyles from '../authEntryShared.module.css';

export interface CreateOrganizationModalProps {
  submitting?: boolean;
  onSubmit: (values: { organizationName: string; inviteTeammates: string }) => void;
  onJoinExisting: () => void;
}

export function CreateOrganizationModal({
  submitting = false,
  onSubmit,
  onJoinExisting,
}: CreateOrganizationModalProps) {
  const [organizationName, setOrganizationName] = useState('');
  const [inviteTeammates, setInviteTeammates] = useState('');
  const [showValidation, setShowValidation] = useState(false);
  const liveRef = useRef<HTMLDivElement>(null);

  const announce = useCallback((message: string) => {
    if (liveRef.current) liveRef.current.textContent = message;
  }, []);

  const organizationError =
    showValidation && !organizationName.trim() ? AUTH_COPY.organizationNameRequired : undefined;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setShowValidation(true);
    if (!organizationName.trim()) {
      announce('Fix the highlighted fields.');
      return;
    }
    onSubmit({ organizationName: organizationName.trim(), inviteTeammates: inviteTeammates.trim() });
  };

  return (
    <form
      className={sharedStyles.form}
      data-create-organization-modal
      noValidate
      onSubmit={handleSubmit}
    >
      <div ref={liveRef} className={sharedStyles.statusLive} aria-live="polite" />
      <header className={sharedStyles.header}>
        <h1 className={sharedStyles.title}>{AUTH_COPY.createOrganizationTitle}</h1>
      </header>

      <FormField
        id="organization-name"
        label={AUTH_COPY.organizationNameLabel}
        type="text"
        autoComplete="organization"
        value={organizationName}
        onChange={(event) => setOrganizationName(event.target.value)}
        disabled={submitting}
        error={organizationError}
      />

      <FormField
        id="invite-teammates"
        label={AUTH_COPY.inviteTeammatesLabel}
        type="text"
        value={inviteTeammates}
        onChange={(event) => setInviteTeammates(event.target.value)}
        disabled={submitting}
        hint={AUTH_COPY.inviteTeammatesHint}
      />

      <SubmitButton loading={submitting} loadingLabel={AUTH_COPY.submitting}>
        {AUTH_COPY.submitCreateOrganization}
      </SubmitButton>

      <p className={sharedStyles.subordinateLink}>
        <button
          type="button"
          className={sharedStyles.subordinateButton}
          onClick={onJoinExisting}
          disabled={submitting}
        >
          {AUTH_COPY.joinExistingOrganization}
        </button>
      </p>
    </form>
  );
}
