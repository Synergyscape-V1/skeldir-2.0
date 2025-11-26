/**
 * SidebarPrimaryContent Component
 * 
 * Renders primary navigation items with glassmorphic treatment.
 * Must be rendered within a SidebarProvider context to access sidebar state.
 */

import { LayoutDashboard, Workflow, TrendingUp, DollarSign } from 'lucide-react';
import { SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarMenu, SidebarMenuItem, useSidebar } from '@/components/ui/sidebar';
import { GlassmorphicUtilityButton } from '@/components/ui/glassmorphic-button';
import { useLocation } from 'wouter';

export function SidebarPrimaryContent() {
  const { state: sidebarState } = useSidebar();
  const isCollapsed = sidebarState === 'collapsed';
  const [, navigate] = useLocation();

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Primary Navigation</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          <SidebarMenuItem>
            <GlassmorphicUtilityButton
              icon={LayoutDashboard}
              label="Dashboard"
              isCollapsed={isCollapsed}
              onClick={() => navigate('/')}
              data-testid="nav-dashboard"
            />
          </SidebarMenuItem>
          <SidebarMenuItem>
            <GlassmorphicUtilityButton
              icon={Workflow}
              label="Implementation Portal"
              isCollapsed={isCollapsed}
              onClick={() => navigate('/implementation-portal')}
              data-testid="nav-implementation"
            />
          </SidebarMenuItem>
          <SidebarMenuItem>
            <GlassmorphicUtilityButton
              icon={TrendingUp}
              label="Channel Performance"
              isCollapsed={isCollapsed}
              onClick={() => navigate('/channel-performance')}
              data-testid="nav-channel"
            />
          </SidebarMenuItem>
          <SidebarMenuItem>
            <GlassmorphicUtilityButton
              icon={DollarSign}
              label="Budget Reallocation"
              isCollapsed={isCollapsed}
              onClick={() => navigate('/budget-reallocation')}
              data-testid="nav-budget"
            />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
