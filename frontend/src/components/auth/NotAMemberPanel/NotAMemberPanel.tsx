import { AUTH_COPY } from '../../../auth/copy';
import sharedStyles from '../authEntryShared.module.css';

export interface NotAMemberPanelProps {
  onCreateOrganization: () => void;
  onCheckEmail: () => void;
}

export function NotAMemberPanel({ onCreateOrganization, onCheckEmail }: NotAMemberPanelProps) {
  return (
    <div className={sharedStyles.form} data-not-a-member-panel role="region" aria-labelledby="not-a-member-title">
      <header className={sharedStyles.header}>
        <h1 id="not-a-member-title" className={sharedStyles.title}>
          {AUTH_COPY.notAMemberTitle}
        </h1>
        <p className={sharedStyles.bodyCopy}>{AUTH_COPY.notAMemberBody}</p>
      </header>

      <div className={sharedStyles.actionStack}>
        <button type="button" className={sharedStyles.secondaryAction} onClick={onCreateOrganization}>
          {AUTH_COPY.notAMemberCreateOrg}
        </button>
        <button type="button" className={sharedStyles.subordinateButton} onClick={onCheckEmail}>
          {AUTH_COPY.notAMemberCheckEmail}
        </button>
      </div>
    </div>
  );
}
