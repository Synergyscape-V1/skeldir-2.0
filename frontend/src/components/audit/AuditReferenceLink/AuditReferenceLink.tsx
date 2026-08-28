import { Link } from 'react-router-dom';
import {
  buildAuditReferenceHref,
  formatAuditReferenceLabel,
} from '../../../detail/auditReference';
import shared from '../../../styles/shared.module.css';
import styles from './AuditReferenceLink.module.css';

export interface AuditReferenceLinkProps {
  auditReference: string;
  envelopeId?: string;
  claimId?: string;
  className?: string;
}

export function AuditReferenceLink({
  auditReference,
  envelopeId,
  claimId,
  className,
}: AuditReferenceLinkProps) {
  const href = buildAuditReferenceHref(auditReference, { envelopeId, claimId });
  const label = formatAuditReferenceLabel(auditReference);

  return (
    <Link
      to={href}
      className={[styles.link, shared.focusVisible, className].filter(Boolean).join(' ')}
      data-audit-reference={auditReference}
      aria-label={`Open audit ledger for ${label}`}
    >
      {label}
    </Link>
  );
}
