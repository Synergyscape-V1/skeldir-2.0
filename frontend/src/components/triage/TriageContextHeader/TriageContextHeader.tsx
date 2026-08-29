import { Link } from 'react-router-dom';

import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import shared from '../../../styles/shared.module.css';
import styles from './TriageContextHeader.module.css';

export interface TriageContextHeaderProps {
  issueIndex: number;
  issueTotal: number;
  title: string;
  exitHref?: string;
}

export function TriageContextHeader({
  issueIndex,
  issueTotal,
  title,
  exitHref = '/app',
}: TriageContextHeaderProps) {
  return (
    <header className={styles.header} data-triage-context-header>
      <div className={styles.left}>
        <Link
          to={exitHref}
          className={[styles.back, shared.focusVisible].join(' ')}
          data-triage-back-to-queue
        >
          {COMMAND_CENTER_COPY.triage.backToQueue}
        </Link>
        <p className={styles.progress} data-triage-progress>
          {COMMAND_CENTER_COPY.triage.resolvingIssue(issueIndex, issueTotal, title)}
        </p>
      </div>
      <Link
        to={exitHref}
        className={[styles.exit, shared.focusVisible].join(' ')}
        data-triage-exit
      >
        {COMMAND_CENTER_COPY.triage.exitTriage}
      </Link>
    </header>
  );
}
