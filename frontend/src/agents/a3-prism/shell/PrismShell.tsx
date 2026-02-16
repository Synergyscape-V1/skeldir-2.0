/**
 * A3-PRISM Application Shell — Split-Pane Cockpit
 *
 * Desktop: resizable left panel (nav + priority context) + right panel (header + content)
 * Mobile: linearized single-column layout
 */

import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { Menu, X, HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import UserAvatar from '@/components/ui/user-avatar';
import { NAV_ITEMS } from '@/config/nav';

function getPageTitle(pathname: string): string {
  return NAV_ITEMS.find((n) => n.path === pathname)?.label ?? 'Skeldir';
}

export function PrismShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();
  const title = getPageTitle(location.pathname);

  return (
    <div className="flex flex-col h-screen w-full bg-background">
      {/* Mobile header */}
      <header
        role="banner"
        className="lg:hidden sticky top-0 z-50 flex h-14 items-center justify-between px-4 border-b border-border bg-card"
      >
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => setMobileNavOpen(v => !v)} aria-label="Toggle navigation" aria-expanded={mobileNavOpen}>
            {mobileNavOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
          <span className="text-sm font-semibold text-foreground">Skeldir</span>
        </div>
        <UserAvatar userName="A. Director" userEmail="director@agency.com" userInitials="AD" />
      </header>

      {/* Mobile nav overlay */}
      {mobileNavOpen && (
        <div className="lg:hidden fixed inset-0 top-14 z-40 bg-background/95 backdrop-blur-sm">
          <nav aria-label="Primary navigation" className="p-4 space-y-1">
            {NAV_ITEMS.map(item => {
              const Icon = item.icon;
              return (
                <NavLink key={item.path} to={item.path} end={item.path === '/'} onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) => cn('flex items-center gap-3 px-4 py-3 rounded-md text-sm font-medium transition-colors duration-200', isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-accent')}>
                  <Icon className="h-5 w-5" /><span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>
      )}

      {/* Desktop: split-pane layout */}
      <div className="hidden lg:flex flex-1 overflow-hidden">
        <ResizablePanelGroup direction="horizontal" className="flex-1">
          {/* Left Panel: Nav + Context */}
          <ResizablePanel defaultSize={22} minSize={16} maxSize={35}>
            <div className="flex flex-col h-full border-r border-border bg-card/50">
              {/* Logo */}
              <div className="h-14 flex items-center px-5 border-b border-border">
                <span className="text-base font-semibold text-foreground tracking-tight">Skeldir</span>
              </div>

              {/* Navigation */}
              <nav aria-label="Primary navigation" className="flex-1 overflow-auto py-3 px-3">
                <div className="space-y-0.5">
                  {NAV_ITEMS.map(item => {
                    const Icon = item.icon;
                    return (
                      <NavLink key={item.path} to={item.path} end={item.path === '/'}
                        className={({ isActive }) => cn(
                          'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-200',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                          isActive ? 'bg-primary/10 text-primary border-l-2 border-primary font-medium' : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                        )}>
                        <Icon className="h-4 w-4" /><span>{item.label}</span>
                      </NavLink>
                    );
                  })}
                </div>
              </nav>

              {/* Blueprint grid pattern (subtle) */}
              <div className="h-px bg-border" />
              <div className="p-4 text-[9px] font-mono text-muted-foreground/40 uppercase tracking-widest">
                PRISM · Adaptive Cockpit
              </div>
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* Right Panel: Header + Content */}
          <ResizablePanel defaultSize={78}>
            <div className="flex flex-col h-full">
              <header role="banner" className="sticky top-0 z-40 flex h-14 items-center justify-between px-6 border-b border-border bg-background/95 backdrop-blur-sm">
                <span className="text-sm font-medium text-foreground">{title}</span>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" asChild>
                    <NavLink to="/help" aria-label="Help"><HelpCircle className="h-4 w-4" /></NavLink>
                  </Button>
                  <UserAvatar userName="A. Director" userEmail="director@agency.com" userInitials="AD" />
                </div>
              </header>
              <main role="main" className="flex-1 overflow-auto">
                <div className="mx-auto max-w-6xl p-6">
                  <Outlet />
                </div>
              </main>
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      {/* Mobile: simple content */}
      <main role="main" className="lg:hidden flex-1 overflow-auto">
        <div className="p-4"><Outlet /></div>
      </main>
    </div>
  );
}
