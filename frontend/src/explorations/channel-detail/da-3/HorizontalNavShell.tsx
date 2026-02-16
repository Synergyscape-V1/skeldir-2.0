/**
 * DA-3 TIMELINE — Horizontal Navigation Shell
 *
 * Transparent/translucent nav bar overlaying the page.
 * Semi-transparent background with backdrop blur for depth.
 * Logo "S" mark left, 6 nav items center, user initials right.
 * Mobile: hamburger menu below 768px.
 *
 * No Tailwind — inline styles only.
 */

import React, { useState, useEffect } from 'react';
import { NAV_ITEMS } from '../shared/types';
import type { NavItem } from '../shared/types';

/* -- Design Tokens -------------------------------------------------------- */
const tokens = {
  bg: {
    nav: 'rgba(10,14,26,0.85)',
    navHover: 'rgba(61,123,245,0.08)',
    navActive: 'rgba(61,123,245,0.12)',
    mobileOverlay: 'rgba(10,14,26,0.96)',
  },
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
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
  },
  motion: {
    micro: '120ms',
    short: '200ms',
  },
} as const;

/* -- Simple icon map (inline SVGs for nav) -------------------------------- */
const NavIcon: React.FC<{ name: string; size?: number; color?: string }> = ({
  name,
  size = 16,
  color = tokens.text.secondary,
}) => {
  const props = {
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
        <svg {...props}>
          <rect x="3" y="3" width="7" height="9" rx="1" />
          <rect x="14" y="3" width="7" height="5" rx="1" />
          <rect x="14" y="12" width="7" height="9" rx="1" />
          <rect x="3" y="16" width="7" height="5" rx="1" />
        </svg>
      );
    case 'Radio':
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="2" />
          <path d="M16.24 7.76a6 6 0 0 1 0 8.49" />
          <path d="M7.76 16.24a6 6 0 0 1 0-8.49" />
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
          <path d="M4.93 19.07a10 10 0 0 1 0-14.14" />
        </svg>
      );
    case 'Database':
      return (
        <svg {...props}>
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
        </svg>
      );
    case 'Wallet':
      return (
        <svg {...props}>
          <rect x="2" y="6" width="20" height="14" rx="2" />
          <path d="M2 10h20" />
          <path d="M16 14h2" />
        </svg>
      );
    case 'Search':
      return (
        <svg {...props}>
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      );
    case 'Settings':
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    default:
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="10" />
        </svg>
      );
  }
};

/* -- Component ------------------------------------------------------------ */

interface HorizontalNavShellProps {
  activeRoute?: string;
}

export const HorizontalNavShell: React.FC<HorizontalNavShellProps> = ({
  activeRoute = '/',
}) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 767px)');
    const handler = (e: MediaQueryListEvent | MediaQueryList) => setIsMobile(e.matches);
    handler(mql);
    mql.addEventListener('change', handler as (e: MediaQueryListEvent) => void);
    return () => mql.removeEventListener('change', handler as (e: MediaQueryListEvent) => void);
  }, []);

  const isActive = (item: NavItem) => {
    if (item.path === '/') return activeRoute === '/';
    return activeRoute.startsWith(item.path);
  };

  const navItemStyle = (item: NavItem): React.CSSProperties => {
    const active = isActive(item);
    const hovered = hoveredId === item.id;
    return {
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '6px 12px',
      borderRadius: '6px',
      background: active ? tokens.bg.navActive : hovered ? tokens.bg.navHover : 'transparent',
      border: 'none',
      cursor: 'pointer',
      fontFamily: tokens.font.body,
      fontSize: '13px',
      fontWeight: active ? 500 : 400,
      color: active ? tokens.text.primary : tokens.text.secondary,
      transition: `all ${tokens.motion.short} ease`,
      position: 'relative',
      textDecoration: 'none',
      whiteSpace: 'nowrap',
    };
  };

  const activeUnderlineStyle = (item: NavItem): React.CSSProperties => ({
    position: 'absolute',
    bottom: '-2px',
    left: '12px',
    right: '12px',
    height: '2px',
    borderRadius: '1px',
    background: isActive(item) ? tokens.brand : 'transparent',
    boxShadow: isActive(item) ? `0 0 8px ${tokens.brand}60` : 'none',
    transition: `all ${tokens.motion.short} ease`,
  });

  return (
    <nav
      role="navigation"
      aria-label="Main navigation"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '56px',
        padding: '0 24px',
        background: tokens.bg.nav,
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: `1px solid ${tokens.border.subtle}`,
      }}
    >
      {/* Left: Logo "S" mark */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          flexShrink: 0,
        }}
      >
        <div
          aria-label="Skeldir home"
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: `linear-gradient(135deg, ${tokens.brand} 0%, #2A5FD4 100%)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: tokens.font.heading,
            fontSize: '16px',
            fontWeight: 700,
            color: '#FFFFFF',
            flexShrink: 0,
          }}
        >
          S
        </div>
      </div>

      {/* Center: Nav items (desktop) */}
      {!isMobile && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              style={navItemStyle(item)}
              onMouseEnter={() => setHoveredId(item.id)}
              onMouseLeave={() => setHoveredId(null)}
              aria-current={isActive(item) ? 'page' : undefined}
            >
              <NavIcon
                name={item.icon}
                size={15}
                color={isActive(item) ? tokens.text.primary : tokens.text.secondary}
              />
              {item.label}
              <span aria-hidden="true" style={activeUnderlineStyle(item)} />
            </button>
          ))}
        </div>
      )}

      {/* Right: User initials (desktop) / Hamburger (mobile) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
        {isMobile ? (
          <button
            type="button"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(!mobileOpen)}
            style={{
              width: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke={tokens.text.primary}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
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
        ) : (
          <div
            aria-label="User menu"
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: tokens.bg.navActive,
              border: `1px solid ${tokens.border.default}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: tokens.font.body,
              fontSize: '12px',
              fontWeight: 600,
              color: tokens.text.primary,
              cursor: 'pointer',
            }}
          >
            AW
          </div>
        )}
      </div>

      {/* Mobile overlay menu */}
      {isMobile && mobileOpen && (
        <div
          style={{
            position: 'fixed',
            top: '56px',
            left: 0,
            right: 0,
            bottom: 0,
            background: tokens.bg.mobileOverlay,
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            padding: '16px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            zIndex: 99,
          }}
        >
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setMobileOpen(false)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '14px 16px',
                borderRadius: '8px',
                background: isActive(item) ? tokens.bg.navActive : 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontFamily: tokens.font.body,
                fontSize: '15px',
                fontWeight: isActive(item) ? 500 : 400,
                color: isActive(item) ? tokens.text.primary : tokens.text.secondary,
                textAlign: 'left',
                width: '100%',
                transition: `background ${tokens.motion.short} ease`,
              }}
              aria-current={isActive(item) ? 'page' : undefined}
            >
              <NavIcon
                name={item.icon}
                size={18}
                color={isActive(item) ? tokens.text.primary : tokens.text.secondary}
              />
              {item.label}
            </button>
          ))}

          {/* Mobile user info */}
          <div
            style={{
              marginTop: 'auto',
              paddingTop: '16px',
              borderTop: `1px solid ${tokens.border.subtle}`,
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '14px 16px',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: tokens.bg.navActive,
                border: `1px solid ${tokens.border.default}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: tokens.font.body,
                fontSize: '12px',
                fontWeight: 600,
                color: tokens.text.primary,
              }}
            >
              AW
            </div>
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '14px',
                color: tokens.text.primary,
              }}
            >
              A. Whitmore
            </span>
          </div>
        </div>
      )}
    </nav>
  );
};

export default HorizontalNavShell;
