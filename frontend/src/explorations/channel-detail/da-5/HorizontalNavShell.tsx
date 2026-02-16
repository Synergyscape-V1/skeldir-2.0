/**
 * DA-5 COMPACT — Ultra-minimal icon-only navigation shell
 *
 * Icon-only nav at desktop, tooltips on hover via title attribute.
 * Slim 48px height. Brand blue active state with circular bg.
 */

import React from 'react';
import { NAV_ITEMS } from '../shared/types';

/* ── Design tokens ─────────────────────────────────────────────── */
const T = {
  page: '#0A0E1A',
  card: '#111827',
  brand: '#3D7BF5',
  textPrimary: '#F0F4FF',
  textSecondary: '#8B9AB8',
  textMuted: '#4A5568',
  borderSubtle: 'rgba(139,154,184,0.12)',
  borderDefault: 'rgba(139,154,184,0.24)',
  micro: '120ms',
  short: '200ms',
};

/* ── Inline SVG icons (simple geometric shapes) ────────────────── */
const NavIcons: Record<string, React.ReactNode> = {
  LayoutDashboard: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="1" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="10" y="1" width="7" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="10" y="6" width="7" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="1" y="10" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  Radio: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="9" cy="9" r="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M4.5 4.5A6.36 6.36 0 0 0 2.5 9c0 1.77.72 3.37 1.88 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M13.5 4.5A6.36 6.36 0 0 1 15.5 9c0 1.77-.72 3.37-1.88 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  Database: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="9" cy="4.5" rx="6" ry="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3 4.5v4c0 1.38 2.69 2.5 6 2.5s6-1.12 6-2.5v-4" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3 8.5v4c0 1.38 2.69 2.5 6 2.5s6-1.12 6-2.5v-4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  Wallet: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1.5" y="4" width="15" height="11" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M1.5 7h15" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="13" cy="10.5" r="1" fill="currentColor" />
      <path d="M4 4V3.5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2V4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  Search: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 12l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  Settings: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="9" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M9 1v2M9 15v2M1 9h2M15 9h2M3.3 3.3l1.4 1.4M13.3 13.3l1.4 1.4M3.3 14.7l1.4-1.4M13.3 4.7l1.4-1.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
};

interface HorizontalNavShellProps {
  activeRoute?: string;
}

export const HorizontalNavShell: React.FC<HorizontalNavShellProps> = ({
  activeRoute = '/',
}) => {
  const [hoveredId, setHoveredId] = React.useState<string | null>(null);

  return (
    <>
      <style>{`
        @import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");
        @media (prefers-reduced-motion: reduce) {
          .da5-nav-item { transition: none !important; }
        }
      `}</style>
      <nav
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 48,
          padding: '0 16px',
          background: T.card,
          borderBottom: `1px solid ${T.borderSubtle}`,
          fontFamily: "'IBM Plex Sans', sans-serif",
          position: 'relative',
          zIndex: 100,
        }}
        role="navigation"
        aria-label="Main navigation"
      >
        {/* Logo mark */}
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 6,
            background: T.brand,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: "'Syne', sans-serif",
            fontWeight: 700,
            fontSize: 14,
            color: '#FFFFFF',
            flexShrink: 0,
          }}
          aria-label="Skeldir home"
        >
          S
        </div>

        {/* Nav items — icon only */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          {NAV_ITEMS.map((item) => {
            const isActive = item.path === activeRoute;
            const isHovered = hoveredId === item.id;
            return (
              <a
                key={item.id}
                href={item.path}
                title={item.label}
                className="da5-nav-item"
                onMouseEnter={() => setHoveredId(item.id)}
                onMouseLeave={() => setHoveredId(null)}
                onClick={(e) => e.preventDefault()}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 36,
                  height: 36,
                  borderRadius: '50%',
                  color: isActive ? T.brand : isHovered ? T.textPrimary : T.textSecondary,
                  background: isActive
                    ? 'rgba(61,123,245,0.12)'
                    : isHovered
                      ? 'rgba(139,154,184,0.08)'
                      : 'transparent',
                  transition: `all ${T.short} ease`,
                  textDecoration: 'none',
                  position: 'relative',
                }}
                aria-current={isActive ? 'page' : undefined}
              >
                {NavIcons[item.icon] || null}
              </a>
            );
          })}
        </div>

        {/* Right section: user initials */}
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'rgba(61,123,245,0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: "'IBM Plex Sans', sans-serif",
            fontWeight: 600,
            fontSize: 11,
            color: T.brand,
            flexShrink: 0,
            cursor: 'pointer',
          }}
          title="Account settings"
          aria-label="User menu"
        >
          AW
        </div>
      </nav>
    </>
  );
};
