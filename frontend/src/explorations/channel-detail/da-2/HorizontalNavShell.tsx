/**
 * DA-2 DOSSIER -- Horizontal Navigation Shell
 *
 * Slim editorial top bar with logo mark, horizontal nav links,
 * breadcrumb trail, and user initials. Collapses to hamburger below 768px.
 * Semantic HTML: <header> wrapping <nav>.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { NAV_ITEMS } from '../shared/types';

/* ── Google Fonts ─────────────────────────────────────────── */
const FONT_LINK_ID = 'da2-google-fonts';
function ensureFonts() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(FONT_LINK_ID)) return;
  const link = document.createElement('link');
  link.id = FONT_LINK_ID;
  link.rel = 'stylesheet';
  link.href =
    'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=Syne:wght@500;600;700&display=swap';
  document.head.appendChild(link);
}

/* ── Design Tokens ────────────────────────────────────────── */
const COLORS = {
  pageBg: '#0A0E1A',
  cardBg: '#111827',
  nestedBg: '#1F2937',
  text: {
    primary: '#F0F4FF',
    secondary: '#8B9AB8',
    muted: '#4A5568',
  },
  brand: '#3D7BF5',
  border: {
    subtle: 'rgba(139,154,184,0.12)',
    default: 'rgba(139,154,184,0.24)',
  },
} as const;

const FONT = {
  heading: "'Syne', sans-serif",
  body: "'IBM Plex Sans', sans-serif",
  mono: "'IBM Plex Mono', monospace",
} as const;

const MOTION = {
  micro: '120ms',
  short: '200ms',
} as const;

/* ── Styles ───────────────────────────────────────────────── */
const styles = {
  header: {
    position: 'sticky' as const,
    top: 0,
    zIndex: 100,
    background: COLORS.cardBg,
    borderBottom: `1px solid ${COLORS.border.subtle}`,
  } as React.CSSProperties,
  inner: {
    display: 'flex',
    alignItems: 'center',
    height: 56,
    padding: '0 24px',
    maxWidth: 1280,
    margin: '0 auto',
    gap: 24,
  } as React.CSSProperties,
  logoMark: {
    fontFamily: FONT.heading,
    fontSize: 20,
    fontWeight: 700,
    color: COLORS.brand,
    lineHeight: 1,
    width: 32,
    height: 32,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 6,
    background: `${COLORS.brand}14`,
    border: `1px solid ${COLORS.brand}33`,
    flexShrink: 0,
    textDecoration: 'none',
    cursor: 'pointer',
  } as React.CSSProperties,
  navList: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    listStyle: 'none',
    margin: 0,
    padding: 0,
    flex: 1,
  } as React.CSSProperties,
  navLink: (isActive: boolean) =>
    ({
      fontFamily: FONT.body,
      fontSize: 13,
      fontWeight: 500,
      color: isActive ? COLORS.text.primary : COLORS.text.secondary,
      textDecoration: 'none',
      padding: '6px 12px',
      borderRadius: 4,
      borderBottom: isActive ? `2px solid ${COLORS.brand}` : '2px solid transparent',
      transition: `color ${MOTION.micro} ease, border-color ${MOTION.micro} ease`,
      cursor: 'pointer',
      background: 'none',
      border: 'none',
      whiteSpace: 'nowrap' as const,
    }) as React.CSSProperties,
  breadcrumb: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    marginLeft: 'auto',
    flexShrink: 0,
  } as React.CSSProperties,
  breadcrumbSegment: {
    fontFamily: FONT.body,
    fontSize: 12,
    fontWeight: 500,
    color: COLORS.text.muted,
  } as React.CSSProperties,
  breadcrumbActive: {
    fontFamily: FONT.body,
    fontSize: 12,
    fontWeight: 500,
    color: COLORS.text.secondary,
  } as React.CSSProperties,
  breadcrumbSep: {
    fontFamily: FONT.body,
    fontSize: 12,
    color: COLORS.text.muted,
    userSelect: 'none' as const,
  } as React.CSSProperties,
  userBadge: {
    width: 32,
    height: 32,
    borderRadius: '50%',
    background: COLORS.nestedBg,
    border: `1px solid ${COLORS.border.default}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: FONT.mono,
    fontSize: 12,
    fontWeight: 600,
    color: COLORS.text.secondary,
    flexShrink: 0,
    cursor: 'pointer',
  } as React.CSSProperties,
  hamburger: {
    display: 'none',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 8,
    marginLeft: 'auto',
    color: COLORS.text.secondary,
    flexShrink: 0,
  } as React.CSSProperties,
  mobileMenu: (isOpen: boolean) =>
    ({
      display: isOpen ? 'flex' : 'none',
      flexDirection: 'column' as const,
      padding: '8px 24px 16px',
      gap: 4,
      background: COLORS.cardBg,
      borderBottom: `1px solid ${COLORS.border.subtle}`,
    }) as React.CSSProperties,
  mobileLink: (isActive: boolean) =>
    ({
      fontFamily: FONT.body,
      fontSize: 14,
      fontWeight: 500,
      color: isActive ? COLORS.text.primary : COLORS.text.secondary,
      textDecoration: 'none',
      padding: '10px 12px',
      borderRadius: 4,
      borderLeft: isActive ? `3px solid ${COLORS.brand}` : '3px solid transparent',
      background: isActive ? `${COLORS.brand}0A` : 'transparent',
      cursor: 'pointer',
      border: 'none',
    }) as React.CSSProperties,
} as const;

/* ── Responsive style injection ──────────────────────────── */
const RESPONSIVE_STYLE_ID = 'da2-nav-responsive';
function ensureResponsiveStyles() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(RESPONSIVE_STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = RESPONSIVE_STYLE_ID;
  style.textContent = `
    @media (max-width: 768px) {
      .da2-nav-desktop { display: none !important; }
      .da2-nav-breadcrumb-desktop { display: none !important; }
      .da2-hamburger-btn { display: flex !important; }
    }
    @media (min-width: 769px) {
      .da2-mobile-menu { display: none !important; }
    }
  `;
  document.head.appendChild(style);
}

/* ── Component ────────────────────────────────────────────── */
interface HorizontalNavShellProps {
  activeRoute?: string;
  breadcrumb?: string[];
}

export const HorizontalNavShell: React.FC<HorizontalNavShellProps> = ({
  activeRoute = '/channels',
  breadcrumb = [],
}) => {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    ensureFonts();
    ensureResponsiveStyles();
  }, []);

  const handleToggle = useCallback(() => {
    setMobileOpen((prev) => !prev);
  }, []);

  return (
    <header style={styles.header}>
      <div style={styles.inner}>
        {/* Logo mark */}
        <span style={styles.logoMark} aria-label="Skeldir home">
          S
        </span>

        {/* Desktop nav */}
        <nav aria-label="Main navigation">
          <ul style={styles.navList} className="da2-nav-desktop">
            {NAV_ITEMS.map((item) => {
              const isActive = item.path === activeRoute;
              return (
                <li key={item.id}>
                  <a
                    href={item.path}
                    style={styles.navLink(isActive)}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {item.label}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Breadcrumb */}
        {breadcrumb.length > 0 && (
          <div
            style={styles.breadcrumb}
            className="da2-nav-breadcrumb-desktop"
            aria-label="Breadcrumb"
            role="navigation"
          >
            {breadcrumb.map((segment, idx) => {
              const isLast = idx === breadcrumb.length - 1;
              return (
                <React.Fragment key={idx}>
                  <span style={isLast ? styles.breadcrumbActive : styles.breadcrumbSegment}>
                    {segment}
                  </span>
                  {!isLast && <span style={styles.breadcrumbSep} aria-hidden="true">&gt;</span>}
                </React.Fragment>
              );
            })}
          </div>
        )}

        {/* User initials */}
        <span style={styles.userBadge} title="User profile" role="button" tabIndex={0}>
          AW
        </span>

        {/* Hamburger (mobile only) */}
        <button
          style={styles.hamburger}
          className="da2-hamburger-btn"
          onClick={handleToggle}
          aria-expanded={mobileOpen}
          aria-controls="da2-mobile-nav"
          aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {mobileOpen ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Mobile dropdown menu */}
      <div
        id="da2-mobile-nav"
        style={styles.mobileMenu(mobileOpen)}
        className="da2-mobile-menu"
        role="navigation"
        aria-label="Mobile navigation"
      >
        {NAV_ITEMS.map((item) => {
          const isActive = item.path === activeRoute;
          return (
            <a
              key={item.id}
              href={item.path}
              style={styles.mobileLink(isActive)}
              aria-current={isActive ? 'page' : undefined}
            >
              {item.label}
            </a>
          );
        })}
        {breadcrumb.length > 0 && (
          <div style={{ padding: '8px 12px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
            {breadcrumb.map((segment, idx) => {
              const isLast = idx === breadcrumb.length - 1;
              return (
                <React.Fragment key={idx}>
                  <span style={isLast ? styles.breadcrumbActive : styles.breadcrumbSegment}>
                    {segment}
                  </span>
                  {!isLast && <span style={styles.breadcrumbSep} aria-hidden="true">&gt;</span>}
                </React.Fragment>
              );
            })}
          </div>
        )}
      </div>
    </header>
  );
};

export default HorizontalNavShell;
