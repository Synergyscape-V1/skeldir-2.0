import { useSidebar } from "@/components/ui/sidebar";
import Final_Skeldir_Logo__image_alone_ from "@assets/Final Skeldir Logo (image alone).png";

export function SidebarBranding() {
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";

  return (
    <div className="relative h-16 overflow-visible flex items-center justify-center">
      {/* Icon-only version for collapsed state */}
      <div 
        className={`absolute flex items-center justify-center motion-safe:transition-all motion-safe:duration-300 motion-safe:ease-out ${
          isCollapsed ? 'opacity-100 scale-100 pointer-events-auto' : 'opacity-0 scale-95 pointer-events-none'
        }`}
        data-testid="logo-sidebar-collapsed"
      >
        <div 
          className="flex items-center justify-center dashboard-logo"
          style={{
            width: '34px',
            height: '34px',
            filter: 'var(--dash-logo-glow)',
            transition: 'filter 300ms ease'
          }}
        >
          <img 
            src={Final_Skeldir_Logo__image_alone_} 
            alt={isCollapsed ? "Skeldir" : ""} 
            aria-hidden={!isCollapsed}
            className="object-contain"
            style={{ width: '34px', height: '34px' }}
          />
        </div>
      </div>
      {/* Full logo with wordmark for expanded state */}
      <div 
        className={`absolute flex items-center motion-safe:transition-all motion-safe:duration-300 motion-safe:ease-out ${
          isCollapsed ? 'opacity-0 scale-95 pointer-events-none' : 'opacity-100 scale-100 pointer-events-auto'
        }`}
        data-testid="logo-sidebar-expanded"
      >
        <div 
          className="flex items-center gap-2 dashboard-logo"
          style={{
            filter: 'var(--dash-logo-glow)',
            transition: 'filter 300ms ease'
          }}
        >
          <img 
            src={Final_Skeldir_Logo__image_alone_} 
            alt={!isCollapsed ? "Skeldir Logo" : ""} 
            aria-hidden={isCollapsed}
            className="h-10 w-auto object-contain"
          />
          <span 
            className="text-lg font-bold tracking-tight"
            style={{ color: 'hsl(var(--brand-cool-black))' }}
          >
            SKELDIR
          </span>
        </div>
      </div>
    </div>
  );
}