/**
 * DA-1 COCKPIT — Horizontal Navigation Shell
 *
 * Full-width command bar with aerospace-inspired styling.
 * Logo "S" mark on left, 6 nav items, live polling dot,
 * user avatar initials on far right.
 *
 * Mobile (<768px): collapses to hamburger menu.
 * Semantic: <header> with <nav>.
 */

import React, { useState, useEffect, useId } from 'react';
import type { NavItem } from '../shared/types';
import { NAV_ITEMS } from '../shared/types';

/* ── Design Tokens ──────────────────────────────────────────────── */
const tokens = {
  bg: {
    page: '#0A0E1A',
    card: '#111827',
    nested: '#1F2937',
    elevated: '#263244',
  },
  text: {
    primary: '#F0F4FF',
    secondary: '#8B9AB8',
    muted: '#4A5568',
  },
  brand: '#3D7BF5',
  confidence: {
    high: '#10D98C',
  },
  border: {
    subtle: 'rgba(139,154,184,0.12)',
    default: 'rgba(139,154,184,0.24)',
  },
  font: {
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  motion: {
    micro: '120ms',
    short: '200ms',
    medium: '300ms',
    breathe: '3000ms',
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
} as const;

/* ── Keyframes ─────────────────────────────────────────────────── */

const KEYFRAMES_ID = 'da1-nav-keyframes';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(KEYFRAMES_ID)) return;

  const style = document.createElement('style');
  style.id = KEYFRAMES_ID;
  style.textContent = `
    @keyframes da1PollingPulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(1.4); }
    }
    @keyframes da1ConfidencePulseNav {
      0%, 100% { box-shadow: 0 0 4px ${tokens.brand}40; }
      50% { box-shadow: 0 0 12px ${tokens.brand}80; }
    }
    @media (prefers-reduced-motion: reduce) {
      .da1-polling-dot, .da1-nav-active {
        animation: none !important;
      }
    }
  `;
  document.head.appendChild(style);
}

/* ── Icon components (inline SVG, Lucide-style) ────────────────── */

const NavIcon: React.FC<{ name: string; size?: number; color?: string }> = ({
  name,
  size = 18,
  color = tokens.text.secondary,
}) => {
  const commonProps = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: color,
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true as const,
  };

  switch (name) {
    case 'LayoutDashboard':
      return (
        <svg {...commonProps}>
          <rect x="3" y="3" width="7" height="9" rx="1" />
          <rect x="14" y="3" width="7" height="5" rx="1" />
          <rect x="14" y="12" width="7" height="9" rx="1" />
          <rect x="3" y="16" width="7" height="5" rx="1" />
        </svg>
      );
    case 'Radio':
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="2" />
          <path d="M16.24 7.76a6 6 0 0 1 0 8.49" />
          <path d="M7.76 16.24a6 6 0 0 1 0-8.49" />
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
          <path d="M4.93 19.07a10 10 0 0 1 0-14.14" />
        </svg>
      );
    case 'Database':
      return (
        <svg {...commonProps}>
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M21 12c0 1.66-4.03 3-9 3s-9-1.34-9-3" />
          <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
        </svg>
      );
    case 'Wallet':
      return (
        <svg {...commonProps}>
          <path d="M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4" />
          <path d="M4 6v12a2 2 0 0 0 2 2h14v-4" />
          <path d="M18 12a2 2 0 0 0 0 4h4v-4h-4z" />
        </svg>
      );
    case 'Search':
      return (
        <svg {...commonProps}>
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
      );
    case 'Settings':
      return (
        <svg {...commonProps}>
          <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
    default:
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="10" />
        </svg>
      );
  }
};

/* ── Hamburger Icon ────────────────────────────────────────────── */

const HamburgerIcon: React.FC<{ open: boolean; color: string }> = ({ open, color }) => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    {open ? (
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
);

/* ── Props ──────────────────────────────────────────────────────── */

interface HorizontalNavShellProps {
  activeRoute?: string;
  onNavigate?: (path: string) => void;
}

/* ── Component ──────────────────────────────────────────────────── */

export const HorizontalNavShell: React.FC<HorizontalNavShellProps> = ({
  activeRoute = '/',
  onNavigate,
}) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const navId = useId();

  useEffect(() => {
    ensureKeyframes();
  }, []);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 768px)');
    const handler = (e: MediaQueryListEvent | MediaQueryList) => setIsMobile(e.matches);
    handler(mql);
    mql.addEventListener('change', handler as (e: MediaQueryListEvent) => void);
    return () => mql.removeEventListener('change', handler as (e: MediaQueryListEvent) => void);
  }, []);

  const handleNavClick = (item: NavItem) => {
    if (onNavigate) onNavigate(item.path);
    setMobileOpen(false);
  };

  return (
    <>
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          width: '100%',
          background: tokens.bg.card,
          borderBottom: `1px solid ${tokens.border.subtle}`,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            height: '56px',
            maxWidth: '1440px',
            margin: '0 auto',
            width: '100%',
            boxSizing: 'border-box',
          }}
        >
          {/* Left: Logo "S" mark */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              flexShrink: 0,
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: `linear-gradient(135deg, ${tokens.brand}, ${tokens.brand}CC)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: tokens.font.body,
                fontSize: '16px',
                fontWeight: 700,
                color: '#FFFFFF',
                letterSpacing: '-0.02em',
                flexShrink: 0,
              }}
              aria-hidden="true"
            >
              S
            </div>

            {/* Desktop nav items */}
            {!isMobile && (
              <nav aria-label="Main navigation" id={navId}>
                <ul
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    listStyle: 'none',
                    margin: 0,
                    padding: 0,
                  }}
                >
                  {NAV_ITEMS.map((item) => {
                    const isActive = activeRoute === item.path;
                    return (
                      <li key={item.id}>
                        <button
                          onClick={() => handleNavClick(item)}
                          className={isActive ? 'da1-nav-active' : undefined}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: 'none',
                            cursor: 'pointer',
                            fontFamily: tokens.font.body,
                            fontSize: '13px',
                            fontWeight: isActive ? 600 : 400,
                            color: isActive ? tokens.text.primary : tokens.text.secondary,
                            background: isActive ? `${tokens.brand}18` : 'transparent',
                            borderBottom: isActive ? `2px solid ${tokens.brand}` : '2px solid transparent',
                            transition: `all ${tokens.motion.short} ${tokens.motion.easing}`,
                            whiteSpace: 'nowrap',
                          }}
                          aria-current={isActive ? 'page' : undefined}
                        >
                          <NavIcon
                            name={item.icon}
                            size={16}
                            color={isActive ? tokens.brand : tokens.text.secondary}
                          />
                          {item.label}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </nav>
            )}
          </div>

          {/* Right section: polling dot + user avatar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
              flexShrink: 0,
            }}
          >
            {/* Live polling dot */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <div
                className="da1-polling-dot"
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: tokens.confidence.high,
                  animation: `da1PollingPulse ${tokens.motion.breathe} ease-in-out infinite`,
                  flexShrink: 0,
                }}
                role="status"
                aria-label="Live data connection active"
              />
              <span
                style={{
                  fontFamily: tokens.font.mono,
                  fontSize: '11px',
                  color: tokens.text.muted,
                  display: isMobile ? 'none' : 'inline',
                }}
              >
                Live
              </span>
            </div>

            {/* User avatar initials */}
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: tokens.bg.elevated,
                border: `1px solid ${tokens.border.default}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: tokens.font.body,
                fontSize: '12px',
                fontWeight: 600,
                color: tokens.text.secondary,
                flexShrink: 0,
                cursor: 'pointer',
              }}
              role="button"
              aria-label="User profile"
              tabIndex={0}
            >
              AW
            </div>

            {/* Mobile hamburger */}
            {isMobile && (
              <button
                onClick={() => setMobileOpen(!mobileOpen)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '36px',
                  height: '36px',
                  padding: 0,
                  border: 'none',
                  borderRadius: '6px',
                  background: mobileOpen ? tokens.bg.nested : 'transparent',
                  cursor: 'pointer',
                }}
                aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
                aria-expanded={mobileOpen}
                aria-controls={`${navId}-mobile`}
              >
                <HamburgerIcon open={mobileOpen} color={tokens.text.primary} />
              </button>
            )}
          </div>
        </div>

        {/* Mobile dropdown nav */}
        {isMobile && mobileOpen && (
          <nav
            id={`${navId}-mobile`}
            aria-label="Main navigation"
            style={{
              borderTop: `1px solid ${tokens.border.subtle}`,
              padding: '8px 24px 16px',
              background: tokens.bg.card,
            }}
          >
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              {NAV_ITEMS.map((item) => {
                const isActive = activeRoute === item.path;
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => handleNavClick(item)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '10px 12px',
                        borderRadius: '6px',
                        border: 'none',
                        cursor: 'pointer',
                        fontFamily: tokens.font.body,
                        fontSize: '14px',
                        fontWeight: isActive ? 600 : 400,
                        color: isActive ? tokens.text.primary : tokens.text.secondary,
                        background: isActive ? `${tokens.brand}18` : 'transparent',
                        width: '100%',
                        textAlign: 'left',
                        transition: `all ${tokens.motion.short} ${tokens.motion.easing}`,
                      }}
                      aria-current={isActive ? 'page' : undefined}
                    >
                      <NavIcon
                        name={item.icon}
                        size={18}
                        color={isActive ? tokens.brand : tokens.text.secondary}
                      />
                      {item.label}
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
        )}
      </header>
    </>
  );
};

export default HorizontalNavShell;
