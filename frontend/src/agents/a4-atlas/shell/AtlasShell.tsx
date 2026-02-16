/**
 * A4-ATLAS Application Shell — Floating Icon Rail + Status Ribbon
 *
 * 32px status ribbon at top. 56px floating translucent icon rail on left.
 * Auto-hides on scroll down, reappears on scroll up.
 * Mobile: rail becomes bottom tab bar.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { HelpCircle, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import UserAvatar from '@/components/ui/user-avatar';
import { NAV_ITEMS } from '@/config/nav';

export function AtlasShell() {
  const [railVisible, setRailVisible] = useState(true);
  const lastScrollY = useRef(0);
  const mainRef = useRef<HTMLElement>(null);

  const handleScroll = useCallback(() => {
    const el = mainRef.current;
    if (!el) return;
    const y = el.scrollTop;
    setRailVisible(y <= 0 || y < lastScrollY.current);
    lastScrollY.current = y;
  }, []);

  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  return (
    <div className="flex flex-col h-screen w-full bg-background">
      {/* Status Ribbon (32px) */}
      <header role="banner" className="flex items-center justify-between h-8 px-4 border-b border-border bg-card text-[11px]">
        <div className="flex items-center gap-2">
          <Activity className="h-3 w-3 text-verified" aria-hidden="true" />
          <span className="text-muted-foreground">System nominal</span>
        </div>
        <span className="font-mono text-muted-foreground tabular-nums" aria-live="polite">
          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-6 w-6" asChild>
            <NavLink to="/help" aria-label="Help"><HelpCircle className="h-3 w-3" /></NavLink>
          </Button>
          <UserAvatar userName="A. Director" userEmail="director@agency.com" userInitials="AD" />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Floating Icon Rail (desktop) */}
        <nav
          aria-label="Primary navigation"
          className={cn(
            'hidden lg:flex flex-col items-center gap-2 w-14 py-3 fixed left-0 top-8 bottom-0 z-30',
            'bg-card/80 backdrop-blur-sm border-r border-border',
            'transition-transform duration-300 ease-in-out',
            railVisible ? 'translate-x-0' : '-translate-x-full'
          )}
          style={{ boxShadow: 'var(--elevation-2)' }}
        >
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <NavLink key={item.path} to={item.path} end={item.path === '/'}
                title={item.label} aria-label={item.label}
                className={({ isActive }) => cn(
                  'flex items-center justify-center w-10 h-10 rounded-md transition-colors duration-200',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isActive ? 'bg-primary/10 text-primary border-l-2 border-primary' : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                )}>
                <Icon className="h-5 w-5" />
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom tab bar (mobile) */}
        <nav aria-label="Primary navigation"
          className="lg:hidden fixed bottom-0 left-0 right-0 z-30 flex items-center justify-around h-14 bg-card border-t border-border">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <NavLink key={item.path} to={item.path} end={item.path === '/'}
                className={({ isActive }) => cn(
                  'flex flex-col items-center justify-center gap-0.5 px-2 py-1 rounded-md text-[9px]',
                  isActive ? 'text-primary' : 'text-muted-foreground'
                )}>
                <Icon className="h-5 w-5" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Main Content */}
        <main ref={mainRef} role="main" className="flex-1 overflow-auto lg:ml-14 pb-16 lg:pb-0">
          <div className="mx-auto max-w-6xl p-4 lg:p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
