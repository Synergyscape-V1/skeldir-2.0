/**
 * A1-SENTINEL Application Shell — Dense Control Room
 *
 * Layout: 64px horizontal command bar → 48px vertical utility rail → main content
 * No traditional sidebar. Navigation as horizontal icon+label buttons.
 *
 * ARIA landmarks:
 *   <header role="banner">       — command bar
 *   <nav aria-label="Primary">   — 6 nav items
 *   <aside aria-label="Utility"> — utility rail
 *   <main role="main">           — Outlet content
 *
 * Responsive:
 *   ≥1024px: full command bar with labels
 *   <1024px: hamburger menu, utility rail hidden
 *
 * Master Skill citations:
 *   - Navigation: 6 top-level items from nav.ts SSOT
 *   - Anti-pattern: no generic stock, no emoji icons
 *   - Accessibility: keyboard nav, focus rings, ARIA
 */

import { useState, useCallback } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import {
  Menu,
  X,
  HelpCircle,
  RefreshCw,
  Bell,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { NAV_ITEMS } from '@/config/nav';
import UserAvatar from '@/components/ui/user-avatar';

export function SentinelShell() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleMenu = useCallback(() => {
    setMobileMenuOpen((v) => !v);
  }, []);

  return (
    <div className="flex flex-col h-screen w-full bg-background">
      {/* ── Command Bar (64px) ── */}
      <header
        role="banner"
        className="sticky top-0 z-50 flex items-center h-16 px-4 border-b border-border bg-card"
        style={{ boxShadow: 'var(--elevation-1)' }}
      >
        {/* Left: Logo + Mobile hamburger */}
        <div className="flex items-center gap-3 min-w-[140px]">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={toggleMenu}
            aria-label={mobileMenuOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={mobileMenuOpen}
            aria-controls="sentinel-mobile-nav"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>

          <span className="text-base font-semibold text-foreground tracking-tight select-none">
            Skeldir
          </span>

          {/* System pulse — subtle activity indicator */}
          <Activity className="h-3 w-3 text-verified opacity-60" aria-hidden="true" />
        </div>

        {/* Center: Navigation (desktop) */}
        <nav
          aria-label="Primary navigation"
          className="hidden lg:flex items-center gap-1 mx-auto"
        >
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-120',
                    'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isActive
                      ? 'bg-primary/10 text-primary border-b-2 border-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  )
                }
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Right: Help + User */}
        <div className="flex items-center gap-2 ml-auto">
          <Button variant="ghost" size="icon" asChild>
            <NavLink to="/help" aria-label="Help and documentation">
              <HelpCircle className="h-4 w-4" />
            </NavLink>
          </Button>
          <UserAvatar
            userName="A. Director"
            userEmail="director@agency.com"
            userInitials="AD"
          />
        </div>
      </header>

      {/* ── Mobile Navigation Overlay ── */}
      {mobileMenuOpen && (
        <div
          id="sentinel-mobile-nav"
          className="lg:hidden fixed inset-0 top-16 z-40 bg-background/95 backdrop-blur-sm"
          role="dialog"
          aria-label="Navigation menu"
        >
          <nav aria-label="Primary navigation" className="p-4 space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/'}
                  onClick={() => setMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-4 py-3 rounded-md text-sm font-medium transition-colors duration-120',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                    )
                  }
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>
      )}

      {/* ── Content Area (Utility Rail + Main) ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Utility Rail (48px, desktop only) */}
        <aside
          aria-label="Utility tools"
          className="hidden lg:flex flex-col items-center gap-2 w-12 py-3 border-r border-border bg-card/50"
        >
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            aria-label="Refresh data"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            aria-label="System status"
          >
            <Activity className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            aria-label="Notifications"
          >
            <Bell className="h-3.5 w-3.5" />
          </Button>
        </aside>

        {/* Main Content */}
        <main role="main" className="flex-1 overflow-auto">
          <div className="mx-auto max-w-6xl p-4 lg:p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
