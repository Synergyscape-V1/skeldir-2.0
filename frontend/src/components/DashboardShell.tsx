import { SidebarProvider, Sidebar, SidebarContent, SidebarTrigger, SidebarInset, SidebarHeader, useSidebar } from "@/components/ui/sidebar";
import { useState, useEffect } from "react";
import { ChevronRight } from "lucide-react";
import "@/assets/brand/colors.css";

interface DashboardShellProps {
  children: React.ReactNode;
  sidebarHeader?: React.ReactNode;
  sidebarContent?: React.ReactNode;
  logo?: React.ReactNode;
  headerActions?: React.ReactNode;
}

function DashboardShellContent({ children, sidebarHeader, sidebarContent, logo, headerActions }: DashboardShellProps) {
  const { state, toggleSidebar, isMobile, setOpenMobile, open } = useSidebar();
  const [scrolled, setScrolled] = useState(false);
  
  useEffect(() => {
    const contentSection = document.querySelector('[role="main"]');
    if (!contentSection) return;

    const handleScroll = () => {
      setScrolled(contentSection.scrollTop > 40);
    };

    contentSection.addEventListener('scroll', handleScroll);
    return () => contentSection.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const sidebarItems = document.querySelectorAll('[role="navigation"] button, [role="navigation"] a');
      const currentFocus = document.activeElement;
      const currentIndex = Array.from(sidebarItems).indexOf(currentFocus as Element);

      if (e.key === 'ArrowDown' && currentIndex >= 0 && currentIndex < sidebarItems.length - 1) {
        e.preventDefault();
        (sidebarItems[currentIndex + 1] as HTMLElement).focus();
      } else if (e.key === 'ArrowUp' && currentIndex > 0) {
        e.preventDefault();
        (sidebarItems[currentIndex - 1] as HTMLElement).focus();
      }

      if (e.key === 'Escape' && isMobile && open) {
        setOpenMobile(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isMobile, open, setOpenMobile]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 375 && isMobile && open) {
        setOpenMobile(false);
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, [open, isMobile, setOpenMobile]);

  useEffect(() => {
    const sidebarNav = document.querySelector('[role="navigation"]');
    if (!sidebarNav) return;

    const buttons = sidebarNav.querySelectorAll('button, a');
    buttons.forEach((button, index) => {
      const labels = button.querySelectorAll('[data-slot="label"], span:not([data-slot="icon"])');
      labels.forEach((label) => {
        (label as HTMLElement).style.transitionDelay = `${index * 50}ms`;
      });
    });
  }, [sidebarContent, state]);
  
  return (
    <div className="flex h-screen w-full relative">
      <Sidebar 
        id="app-sidebar"
        collapsible="icon"
        className={`dashboard-sidebar glass-container ${state === 'expanded' ? 'sidebar-expanded' : 'sidebar-collapsed'}`}
      >
        {sidebarHeader && (
          <SidebarHeader className={state === 'expanded' ? '' : 'sidebar-collapsed-header'}>
            {sidebarHeader}
          </SidebarHeader>
        )}
        <SidebarContent 
          role="navigation" 
          aria-label="Primary navigation"
          className={state === 'expanded' ? 'sidebar-items-expanded' : 'sidebar-items-collapsed'}
        >
          {sidebarContent}
        </SidebarContent>
      </Sidebar>

      <SidebarInset className="flex flex-col flex-1">
        <header 
          role="banner"
          className={`sticky top-0 z-50 dashboard-header ${scrolled ? 'scrolled' : ''}`}
          style={{
            height: '64px',
            position: 'relative'
          }}
        >
          <div className="dashboard-header-gradient" />
          <div 
            className="flex items-center justify-between h-full relative z-10"
            style={{
              paddingLeft: 'var(--spacing-golden-md)',
              paddingRight: 'var(--spacing-golden-md)'
            }}
          >
            <div className="flex items-center gap-4">
              <button
                onClick={toggleSidebar}
                aria-controls="app-sidebar"
                aria-expanded={state === "expanded"}
                data-testid="button-sidebar-toggle"
                className="flex items-center justify-center p-2 rounded hover-elevate active-elevate-2 transition-transform duration-200"
                style={{
                  color: 'hsl(var(--brand-cool-black))'
                }}
              >
                <ChevronRight 
                  className="h-5 w-5"
                  style={{
                    transform: state === "expanded" ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 250ms cubic-bezier(0.4, 0, 0.2, 1)'
                  }}
                />
              </button>
              {logo && (
                <div className="dashboard-logo flex items-center" data-testid="dashboard-logo">
                  {logo}
                </div>
              )}
            </div>
            {headerActions && (
              <div className="flex items-center gap-2">
                {headerActions}
              </div>
            )}
          </div>
        </header>

        <section 
          className="flex-1 overflow-auto dashboard-content"
          role="main"
          aria-labelledby="dashboard-content"
        >
          <div 
            className="mx-auto"
            style={{ 
              maxWidth: '1200px',
              padding: 'var(--spacing-golden-md)',
              paddingTop: 'var(--spacing-golden-lg)',
              paddingBottom: 'var(--spacing-golden-xl)'
            }}
          >
            <h2 id="dashboard-content" className="sr-only">Dashboard Content</h2>
            {children}
          </div>
        </section>
      </SidebarInset>
    </div>
  );
}

export default function DashboardShell({ children, sidebarHeader, sidebarContent, logo, headerActions }: DashboardShellProps) {
  return (
    <SidebarProvider>
      <DashboardShellContent sidebarHeader={sidebarHeader} sidebarContent={sidebarContent} logo={logo} headerActions={headerActions}>
        {children}
      </DashboardShellContent>
    </SidebarProvider>
  );
}
