/**
 * A5-FORGE Application Shell — Tabbed Workspace + Persistent Status Bar
 *
 * 48px top header (logo + user). 48px horizontal tab bar (6 nav items as workspace tabs).
 * 28px persistent status bar at bottom (polling status, last-updated, system health).
 * No sidebar — all navigation is horizontal.
 *
 * The forge metaphor: an industrial workspace where tools are organized in a tab rail
 * and status readouts line the bottom edge — always visible, always current.
 */

import { useEffect, useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { Anvil, Activity, Wifi } from 'lucide-react';
import { cn } from '@/lib/utils';
import UserAvatar from '@/components/ui/user-avatar';
import { NAV_ITEMS } from '@/config/nav';

export function ForgeShell() {
  const [time, setTime] = useState(() => new Date());

  // Update clock every 30 seconds
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex flex-col h-screen w-full bg-background">
      {/* Header (48px) */}
      <header role="banner" className="flex items-center justify-between h-12 px-4 border-b border-border bg-card">
        <div className="flex items-center gap-2">
          <Anvil className="h-5 w-5 text-primary" aria-hidden="true" />
          <span className="text-sm font-semibold text-foreground tracking-tight">FORGE</span>
        </div>
        <UserAvatar userName="A. Director" userEmail="director@agency.com" userInitials="AD" />
      </header>

      {/* Tab Bar (48px) — desktop */}
      <nav
        aria-label="Primary navigation"
        className="hidden md:flex items-end h-12 px-4 border-b border-border bg-card"
      >
        {NAV_ITEMS.map(item => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => cn(
                'flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors duration-200',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                isActive
                  ? 'border-primary text-primary bg-primary/5'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Mobile nav — bottom tabs */}
      <nav
        aria-label="Primary navigation"
        className="md:hidden fixed bottom-7 left-0 right-0 z-30 flex items-center justify-around h-14 bg-card border-t border-border"
      >
        {NAV_ITEMS.map(item => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => cn(
                'flex flex-col items-center justify-center gap-0.5 px-2 py-1 rounded-md text-[9px]',
                isActive ? 'text-primary' : 'text-muted-foreground'
              )}
            >
              <Icon className="h-5 w-5" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Main Content */}
      <main role="main" className="flex-1 overflow-auto pb-7 md:pb-7">
        <div className="mx-auto max-w-7xl p-4 lg:p-6">
          <Outlet />
        </div>
      </main>

      {/* Status Bar (28px) */}
      <footer
        className="flex items-center justify-between h-7 px-4 border-t border-border bg-card text-[11px]"
        role="contentinfo"
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <Wifi className="h-3 w-3 text-verified" aria-hidden="true" />
            <span className="text-muted-foreground">Connected</span>
          </div>
          <span className="text-border">|</span>
          <div className="flex items-center gap-1">
            <Activity className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
            <span className="text-muted-foreground">Polling active</span>
          </div>
        </div>
        <span className="font-mono text-muted-foreground tabular-nums">
          {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      </footer>
    </div>
  );
}
