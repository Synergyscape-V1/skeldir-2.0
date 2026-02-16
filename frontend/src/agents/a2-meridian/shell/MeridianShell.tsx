/**
 * A2-MERIDIAN Application Shell — Spacious Executive Brief
 *
 * Full-height sidebar (256px / 64px collapsed) with grouped sections.
 * Minimal header: breadcrumb-style page name + timestamp + avatar.
 * Generous whitespace, premium feel.
 *
 * Nav groups:
 *   Operations: Command Center, Channels, Budget
 *   Intelligence: Data, Investigations
 *   Administration: Settings
 */

import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { HelpCircle, Menu } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  SidebarProvider,
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarInset,
  useSidebar,
} from '@/components/ui/sidebar';
import { SidebarBranding } from '@/components/SidebarBranding';
import UserAvatar from '@/components/ui/user-avatar';
import { NAV_ITEMS } from '@/config/nav';

const NAV_GROUPS = [
  { label: 'Operations', items: ['/', '/channels', '/budget'] },
  { label: 'Intelligence', items: ['/data', '/investigations'] },
  { label: 'Administration', items: ['/settings'] },
] as const;

function getPageTitle(pathname: string): string {
  const item = NAV_ITEMS.find((n) => n.path === pathname);
  return item?.label ?? 'Skeldir';
}

function MeridianShellContent() {
  const { toggleSidebar, open } = useSidebar();
  const location = useLocation();
  const pageTitle = getPageTitle(location.pathname);

  return (
    <div className="flex h-screen w-full relative">
      <Sidebar collapsible="icon" className="border-r border-sidebar-border">
        <SidebarHeader>
          <SidebarBranding />
        </SidebarHeader>

        <SidebarContent role="navigation" aria-label="Primary navigation">
          {NAV_GROUPS.map((group) => {
            const groupItems = NAV_ITEMS.filter((n) => (group.items as readonly string[]).includes(n.path));
            if (groupItems.length === 0) return null;

            return (
              <div key={group.label} className="mb-4">
                <div className="px-4 py-2 text-[10px] font-medium text-muted-foreground uppercase tracking-widest">
                  {group.label}
                </div>
                <SidebarMenu>
                  {groupItems.map((item) => {
                    const Icon = item.icon;
                    return (
                      <SidebarMenuItem key={item.path}>
                        <SidebarMenuButton asChild tooltip={item.label}>
                          <NavLink
                            to={item.path}
                            end={item.path === '/'}
                            className={({ isActive }) =>
                              cn(
                                'transition-colors duration-200',
                                isActive
                                  ? 'border-l-2 border-primary bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                                  : ''
                              )
                            }
                          >
                            <Icon />
                            <span>{item.label}</span>
                          </NavLink>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    );
                  })}
                </SidebarMenu>
              </div>
            );
          })}
        </SidebarContent>
      </Sidebar>

      <SidebarInset className="flex flex-col flex-1">
        <header
          role="banner"
          className="sticky top-0 z-50 flex h-14 items-center justify-between px-8 border-b border-border bg-background/95 backdrop-blur-sm"
        >
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSidebar}
              className="lg:hidden"
              aria-label="Toggle sidebar"
              aria-expanded={open}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <span className="text-sm font-medium text-foreground">{pageTitle}</span>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" asChild>
              <NavLink to="/help" aria-label="Help">
                <HelpCircle className="h-4 w-4" />
              </NavLink>
            </Button>
            <UserAvatar userName="A. Director" userEmail="director@agency.com" userInitials="AD" />
          </div>
        </header>

        <main role="main" className="flex-1 overflow-auto bg-background">
          <div className="mx-auto max-w-6xl px-8 py-8">
            <Outlet />
          </div>
        </main>
      </SidebarInset>
    </div>
  );
}

export function MeridianShell() {
  return (
    <SidebarProvider>
      <MeridianShellContent />
    </SidebarProvider>
  );
}
