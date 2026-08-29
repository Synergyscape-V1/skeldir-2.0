import type { ImgHTMLAttributes, SVGProps } from 'react';
import checkmarkIcon from '../../assets/icons/nav/checkmark.svg';
import refreshIcon from '../../assets/icons/nav/refresh.svg';

type IconProps = SVGProps<SVGSVGElement> & { title?: string };
type NavIconProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'alt'> & {
  size?: number;
};

export function IconCheckmark({ size = 20, className, ...props }: NavIconProps) {
  return (
    <img
      src={checkmarkIcon}
      alt=""
      aria-hidden
      width={size}
      height={size}
      className={className}
      draggable={false}
      {...props}
    />
  );
}

export function IconSuccess({ title = 'Success', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <circle cx="10" cy="10" r="9" fill="currentColor" opacity="0.15" />
      <path d="M6 10.5l2.5 2.5L14 7.5" stroke="currentColor" strokeWidth="2" fill="none" />
    </svg>
  );
}

export function IconWarning({ title = 'Warning', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path d="M10 3l8 14H2L10 3z" fill="currentColor" opacity="0.15" />
      <path d="M10 8v4M10 14h.01" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

export function IconError({ title = 'Error', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <circle cx="10" cy="10" r="9" fill="currentColor" opacity="0.15" />
      <path d="M7 7l6 6M13 7l-6 6" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

export function IconInfo({ title = 'Information', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" fill="none" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M13 8C13 7.44772 12.5523 7 12 7C11.4477 7 11 7.44772 11 8C11 8.55228 11.4477 9 12 9C12.5523 9 13 8.55228 13 8Z"
        fill="currentColor"
      />
      <path
        d="M12 17.75C12.4142 17.75 12.75 17.4142 12.75 17V11C12.75 10.5858 12.4142 10.25 12 10.25C11.5858 10.25 11.25 10.5858 11.25 11V17C11.25 17.4142 11.5858 17.75 12 17.75Z"
        fill="currentColor"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12.0574 1.25H11.9426C9.63424 1.24999 7.82519 1.24998 6.41371 1.43975C4.96897 1.63399 3.82895 2.03933 2.93414 2.93414C2.03933 3.82895 1.63399 4.96897 1.43975 6.41371C1.24998 7.82519 1.24999 9.63422 1.25 11.9426V12.0574C1.24999 14.3658 1.24998 16.1748 1.43975 17.5863C1.63399 19.031 2.03933 20.1711 2.93414 21.0659C3.82895 21.9607 4.96897 22.366 6.41371 22.5603C7.82519 22.75 9.63423 22.75 11.9426 22.75H12.0574C14.3658 22.75 16.1748 22.75 17.5863 22.5603C19.031 22.366 20.1711 21.9607 21.0659 21.0659C21.9607 20.1711 22.366 19.031 22.5603 17.5863C22.75 16.1748 22.75 14.3658 22.75 12.0574V11.9426C22.75 9.63423 22.75 7.82519 22.5603 6.41371C22.366 4.96897 21.9607 3.82895 21.0659 2.93414C20.1711 2.03933 19.031 1.63399 17.5863 1.43975C16.1748 1.24998 14.3658 1.24999 12.0574 1.25ZM3.9948 3.9948C4.56445 3.42514 5.33517 3.09825 6.61358 2.92637C7.91356 2.75159 9.62177 2.75 12 2.75C14.3782 2.75 16.0864 2.75159 17.3864 2.92637C18.6648 3.09825 19.4355 3.42514 20.0052 3.9948C20.5749 4.56445 20.9018 5.33517 21.0736 6.61358C21.2484 7.91356 21.25 9.62177 21.25 12C21.25 14.3782 21.2484 16.0864 21.0736 17.3864C20.9018 18.6648 20.5749 19.4355 20.0052 20.0052C19.4355 20.5749 18.6648 20.9018 17.3864 21.0736C16.0864 21.2484 14.3782 21.25 12 21.25C9.62177 21.25 7.91356 21.2484 6.61358 21.0736C5.33517 20.9018 4.56445 20.5749 3.9948 20.0052C3.42514 19.4355 3.09825 18.6648 2.92637 17.3864C2.75159 16.0864 2.75 14.3782 2.75 12C2.75 9.62177 2.75159 7.91356 2.92637 6.61358C3.09825 5.33517 3.42514 4.56445 3.9948 3.9948Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function IconShield({ title = 'Authority', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path d="M10 2l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V5l7-3z" fill="currentColor" opacity="0.15" />
      <path d="M10 2l7 3v5c0 4-3 7-7 8" stroke="currentColor" strokeWidth="1.5" fill="none" />
    </svg>
  );
}

export function IconAttributionModel({ title = 'Attribution model', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <circle cx="4" cy="5" r="2" fill="currentColor" />
      <circle cx="16" cy="5" r="2" fill="currentColor" />
      <circle cx="10" cy="15" r="2" fill="currentColor" />
      <path
        d="M5.5 6.2 8.5 13M14.5 6.2 11.5 13M6.2 5.5h7.6"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconConfidenceMetadata({ title = 'Confidence metadata', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z"
        fill="currentColor"
        opacity="0.12"
      />
      <path
        d="M10 3a7 7 0 1 0 0 14"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
      />
      <path
        d="M10 6v4l2.5 2.5"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="10" r="1.25" fill="currentColor" />
    </svg>
  );
}

export function IconBenchmarkMetadata({ title = 'Benchmark metadata', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <rect x="3" y="11" width="3.5" height="6" rx="0.75" fill="currentColor" opacity="0.35" />
      <rect x="8.25" y="7" width="3.5" height="10" rx="0.75" fill="currentColor" opacity="0.55" />
      <rect x="13.5" y="4" width="3.5" height="13" rx="0.75" fill="currentColor" />
    </svg>
  );
}

export function IconPolicyAuthority({ title = 'Policy authority', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path d="M10 2l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V5l7-3z" fill="currentColor" opacity="0.15" />
      <path d="M10 2l7 3v5c0 4-3 7-7 8" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M7 10.5l2 2 4-4.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconProhibited({ title = 'Blocked', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M4.5 11.5 11.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconProvenanceChain({ title = 'Provenance chain', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M7.5 5.5h5M7.5 10h5M7.5 14.5h5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <circle cx="4.5" cy="5.5" r="1.5" fill="currentColor" />
      <circle cx="4.5" cy="10" r="1.5" fill="currentColor" />
      <circle cx="4.5" cy="14.5" r="1.5" fill="currentColor" />
    </svg>
  );
}

export function IconAuditSignature({ title = 'Audit and signature', ...props }: IconProps) {
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path d="M10 2l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V5l7-3z" fill="currentColor" opacity="0.15" />
      <path d="M10 2l7 3v5c0 4-3 7-7 8" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M7 10.5l2 2 4-4.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconChevronRight({ title, ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M5 3.5 10 8 5 12.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Submit / send — vertical arrow for chat composer. */
export function IconArrowUp({ title = 'Send', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M8 12.5V3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4.5 7 8 3.5 11.5 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Internal jump / in-app navigate — diagonal up-right arrow (no external-box). */
export function IconArrowUpRight({ title = 'Navigate', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M4.5 11.5 11.5 4.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M6.5 4.5H11.5V9.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconChevronDown({ title, ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M3.5 5.5 8 10 12.5 5.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconBuilding({ title = 'Workspace', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M2.5 14V5.5L8 2.5l5.5 3V14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M6 14v-3.5h4V14" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function IconTrendUp({ title, ...props }: IconProps) {
  return (
    <svg width={18} height={18} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M4 10 8 5 12 10"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconTrendDown({ title, ...props }: IconProps) {
  return (
    <svg width={18} height={18} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M4 6 8 11 12 6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconTrendNeutral({ title, ...props }: IconProps) {
  return (
    <svg width={18} height={18} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M4 8 12 8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconSearch({ title = 'Search', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" fill="none" strokeWidth="1.5" />
      <path d="M10.5 10.5 14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconCalendar({ title = 'Date range', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <rect x="2" y="3" width="12" height="11" rx="1.5" stroke="currentColor" fill="none" strokeWidth="1.5" />
      <path d="M2 6.5h12M5 1.5v2M11 1.5v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconCopy({ title = 'Copy', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <rect x="5" y="5" width="9" height="9" rx="1" stroke="currentColor" fill="none" />
      <path d="M3 11V3h8" stroke="currentColor" fill="none" />
    </svg>
  );
}

export function IconDownload({ title = 'Download', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path d="M8 2.5v7M5.5 7 8 9.5 10.5 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <path d="M3 12.5h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconFilePlus({ title = 'Open document', ...props }: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path d="M4 2.5h5.5L12 5v8.5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Z" stroke="currentColor" fill="none" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M8 2.5V5.5H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 8.5v3M6.5 10h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconEnvelope({ title = 'TrustEnvelope', ...props }: IconProps) {
  return (
    <svg width={18} height={18} viewBox="0 0 18 18" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <rect x="2.5" y="4.5" width="13" height="9" rx="1.5" stroke="currentColor" fill="none" strokeWidth="1.5" />
      <path d="M2.5 6.5 9 10.5 15.5 6.5" stroke="currentColor" fill="none" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

export function IconClock({ title = 'Time', ...props }: IconProps) {
  return (
    <svg width={18} height={18} viewBox="0 0 18 18" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <circle cx="9" cy="9" r="6.5" stroke="currentColor" fill="none" strokeWidth="1.5" />
      <path d="M9 5.5V9l2.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconRefresh({ size = 16, className, ...props }: NavIconProps) {
  return (
    <img
      src={refreshIcon}
      alt=""
      aria-hidden
      width={size}
      height={size}
      className={className}
      draggable={false}
      {...props}
    />
  );
}

export function IconExternalLink({ title = 'Opens related resource', ...props }: IconProps) {
  return (
    <svg width={14} height={14} viewBox="0 0 14 14" aria-hidden={title ? undefined : true} {...props}>
      {title ? <title>{title}</title> : null}
      <path
        d="M9.5 2.5H11.5V4.5"
        stroke="currentColor"
        fill="none"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M6 8 11.5 2.5M8 2.5h3.5V6"
        stroke="currentColor"
        fill="none"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M11 7.5v4a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1v-6.5a1 1 0 0 1 1-1H7"
        stroke="currentColor"
        fill="none"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
