/**
 * DA-4 ANALYST — Horizontal Nav Shell
 *
 * IDE-tabbed top bar with keyboard shortcut hints.
 * Developer-tool aesthetic: each nav item styled like an IDE tab.
 */

import React, { useState } from 'react';
import { NAV_ITEMS } from '../shared/types';

const FONT_IMPORT = '@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");';

const tokens = {
  bg: { page: '#0A0E1A', card: '#111827', nested: '#1F2937', elevated: '#263244' },
  text: { primary: '#F0F4FF', secondary: '#8B9AB8', muted: '#4A5568' },
  brand: '#3D7BF5',
  border: { subtle: 'rgba(139,154,184,0.12)', default: 'rgba(139,154,184,0.24)' },
};

const SHORTCUT_KEYS = ['⌘1', '⌘2', '⌘3', '⌘4', '⌘5', '⌘6'];

interface HorizontalNavShellProps {
  activeRoute?: string;
}

export const HorizontalNavShell: React.FC<HorizontalNavShellProps> = ({ activeRoute = '/' }) => {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <style>{FONT_IMPORT}</style>
      <style>{`
        @media (max-width: 768px) {
          .da4-nav-tabs { display: none !important; }
          .da4-hamburger { display: flex !important; }
          .da4-mobile-menu { display: ${mobileOpen ? 'flex' : 'none'} !important; }
        }
        @media (min-width: 769px) {
          .da4-hamburger { display: none !important; }
          .da4-mobile-menu { display: none !important; }
        }
      `}</style>
      <header
        style={{
          display: 'flex',
          alignItems: 'stretch',
          height: '48px',
          background: tokens.bg.card,
          borderBottom: `1px solid ${tokens.border.subtle}`,
          fontFamily: "'IBM Plex Sans', sans-serif",
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        {/* Logo */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '0 16px',
            borderRight: `1px solid ${tokens.border.subtle}`,
          }}
        >
          <span
            style={{
              fontFamily: "'Syne', sans-serif",
              fontWeight: 700,
              fontSize: '18px',
              color: tokens.brand,
            }}
          >
            S
          </span>
        </div>

        {/* Tabs */}
        <nav className="da4-nav-tabs" style={{ display: 'flex', alignItems: 'stretch', flex: 1 }} aria-label="Main navigation">
          {NAV_ITEMS.map((item, i) => {
            const isActive = activeRoute === item.path;
            return (
              <a
                key={item.id}
                href={item.path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '0 16px',
                  fontSize: '13px',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? tokens.text.primary : tokens.text.secondary,
                  background: isActive ? tokens.bg.nested : 'transparent',
                  borderRight: `1px solid ${tokens.border.subtle}`,
                  borderBottom: isActive ? `2px solid ${tokens.brand}` : '2px solid transparent',
                  textDecoration: 'none',
                  whiteSpace: 'nowrap',
                  transition: 'background 200ms, color 200ms',
                }}
                aria-current={isActive ? 'page' : undefined}
              >
                {item.label}
                <span
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '10px',
                    color: tokens.text.muted,
                    background: tokens.bg.page,
                    padding: '1px 4px',
                    borderRadius: '3px',
                  }}
                >
                  {SHORTCUT_KEYS[i]}
                </span>
              </a>
            );
          })}
        </nav>

        {/* Hamburger */}
        <button
          className="da4-hamburger"
          onClick={() => setMobileOpen(!mobileOpen)}
          style={{
            display: 'none',
            alignItems: 'center',
            justifyContent: 'center',
            width: '48px',
            background: 'none',
            border: 'none',
            color: tokens.text.primary,
            cursor: 'pointer',
            fontSize: '20px',
          }}
          aria-label="Toggle navigation menu"
        >
          {mobileOpen ? '✕' : '☰'}
        </button>

        {/* User */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '0 16px',
            marginLeft: 'auto',
          }}
        >
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '4px',
              background: tokens.bg.elevated,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '11px',
              fontWeight: 600,
              color: tokens.text.secondary,
              fontFamily: "'IBM Plex Mono', monospace",
            }}
          >
            AY
          </div>
        </div>
      </header>

      {/* Mobile dropdown */}
      <div
        className="da4-mobile-menu"
        style={{
          display: 'none',
          flexDirection: 'column',
          background: tokens.bg.card,
          borderBottom: `1px solid ${tokens.border.subtle}`,
          position: 'sticky',
          top: '48px',
          zIndex: 99,
        }}
      >
        {NAV_ITEMS.map((item) => {
          const isActive = activeRoute === item.path;
          return (
            <a
              key={item.id}
              href={item.path}
              style={{
                padding: '12px 16px',
                color: isActive ? tokens.text.primary : tokens.text.secondary,
                background: isActive ? tokens.bg.nested : 'transparent',
                textDecoration: 'none',
                fontSize: '14px',
                borderLeft: isActive ? `3px solid ${tokens.brand}` : '3px solid transparent',
              }}
            >
              {item.label}
            </a>
          );
        })}
      </div>
    </>
  );
};

export default HorizontalNavShell;
