/**
 * SidebarUtilitiesContent Component
 * 
 * Renders the utility navigation section with glassmorphic buttons.
 * Must be rendered within a SidebarProvider context to access sidebar state.
 */

import { LogOut, HelpCircle, UserCircle, Settings } from 'lucide-react';
import { SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarMenu, SidebarMenuItem, useSidebar } from '@/components/ui/sidebar';
import { GlassmorphicUtilityButton } from '@/components/ui/glassmorphic-button';

interface SidebarUtilitiesContentProps {
  onLogout: () => void;
  isLoggingOut: boolean;
}

export function SidebarUtilitiesContent({ onLogout, isLoggingOut }: SidebarUtilitiesContentProps) {
  const { state: sidebarState } = useSidebar();
  const isCollapsed = sidebarState === 'collapsed';

  return (
    <SidebarGroup className="mt-auto">
      <SidebarGroupLabel>Utilities</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          <SidebarMenuItem>
            <GlassmorphicUtilityButton
              icon={Settings}
              label="Settings"
              isCollapsed={isCollapsed}
              data-testid="nav-settings"
            />
          </SidebarMenuItem>
          <SidebarMenuItem>
            <GlassmorphicUtilityButton
              icon={UserCircle}
              label="Account Info"
              isCollapsed={isCollapsed}
              data-testid="nav-account"
            />
          </SidebarMenuItem>
          <SidebarMenuItem>
            <GlassmorphicUtilityButton
              icon={HelpCircle}
              label="Help"
              isCollapsed={isCollapsed}
              data-testid="nav-help"
            />
          </SidebarMenuItem>
          <SidebarMenuItem className="mt-3">
            <GlassmorphicUtilityButton
              icon={LogOut}
              label="Sign Out"
              isCollapsed={isCollapsed}
              isLoading={isLoggingOut}
              loadingText="Signing Out..."
              onClick={onLogout}
              data-testid="nav-logout"
            />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
