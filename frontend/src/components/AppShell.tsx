/**
 * D3.1 Application Shell — Persistent Authenticated App Chassis
 * 
 * Semantic structure: <header>, <aside>, <main> with ARIA landmarks
 * Navigation: 6-item SSOT with Button(ghost) + NavLink for active-route highlighting
 * Responsive: Fixed sidebar ≥1024px, collapsible <1024px
 * Header affordances: Logo, Help, Profile, Hamburger (mobile)
 * Token-true styling: All colors/spacing from CSS variables
 */

import { Outlet, NavLink } from 'react-router-dom'
import { HelpCircle, Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  SidebarProvider,
  Sidebar,
  SidebarContent,
  SidebarInset,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  useSidebar,
} from '@/components/ui/sidebar'
import { NAV_ITEMS } from '@/config/nav'
import { HeaderLogo } from '@/components/HeaderLogo'
import UserAvatar from '@/components/ui/user-avatar'
import { useCurrentUser } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

function AppShellContent() {
  const { toggleSidebar, open } = useSidebar()
  const user = useCurrentUser()

  return (
    <div className="flex h-screen w-full relative">
      <Sidebar
        id="app-sidebar"
        collapsible="icon"
        className="border-r border-sidebar-border"
      >
        <SidebarContent role="navigation" aria-label="Primary navigation">
          <SidebarMenu className="px-2 py-4 gap-0.5">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              return (
                <SidebarMenuItem key={item.path}>
                  <SidebarMenuButton asChild tooltip={item.label}>
                    <NavLink
                      to={item.path}
                      end={item.path === '/'}
                      className={({ isActive }) =>
                        cn(
                          'transition-all duration-200 ease-in-out',
                          isActive
                            ? 'border-l-2 border-primary bg-sidebar-accent text-sidebar-accent-foreground font-semibold shadow-sm'
                            : 'text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50'
                        )
                      }
                    >
                      <Icon className="size-4 shrink-0 transition-transform duration-200 group-hover/menu-item:scale-105" />
                      <span className="text-sm font-medium tracking-tight transition-colors duration-200">{item.label}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )
            })}
          </SidebarMenu>
        </SidebarContent>
      </Sidebar>

      <SidebarInset className="flex flex-col flex-1">
        <header
          role="banner"
          className="sticky top-0 z-50 flex h-16 items-center justify-between px-6 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80"
        >
          <div className="flex items-center gap-4">
            {/* Hamburger for mobile (<768px per directive) and sidebar toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSidebar}
              className="lg:hidden"
              aria-label="Toggle sidebar"
              aria-controls="app-sidebar"
              aria-expanded={open}
            >
              <Menu className="h-5 w-5" />
            </Button>

            {/* Desktop sidebar toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSidebar}
              className="hidden lg:flex"
              aria-label="Toggle sidebar"
              aria-controls="app-sidebar"
              aria-expanded={open}
            >
              <Menu className="h-5 w-5" />
            </Button>

            {/* Logo - always visible, resizable */}
            <HeaderLogo size="md" className="ml-2" />
          </div>

          <div className="flex items-center gap-2">
            {/* Help button */}
            <Button variant="ghost" size="icon" asChild>
              <NavLink to="/help" aria-label="Help">
                <HelpCircle className="h-5 w-5" />
              </NavLink>
            </Button>

            {/* Profile/User avatar */}
            {user ? (
              <UserAvatar
                userName={user.username}
                userEmail={user.email}
                userInitials={user.username.charAt(0)}
              />
            ) : (
              <Button variant="ghost" size="icon">
                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                  <span className="text-sm font-medium">?</span>
                </div>
              </Button>
            )}
          </div>
        </header>

        <main
          role="main"
          className="flex-1 overflow-auto bg-background"
        >
          <div className="mx-auto max-w-7xl p-6">
            <Outlet />
          </div>
        </main>
      </SidebarInset>
    </div>
  )
}

export default function AppShell() {
  return (
    <SidebarProvider>
      <AppShellContent />
    </SidebarProvider>
  )
}
