import { useState } from "react";
import { useSidebar } from "@/components/ui/sidebar";
import skeldirLogoShield from "@assets/brand/logo-shield.png";
import skeldirLogoSvg from "@assets/brand/logo.svg";

export function SidebarBranding() {
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";
  const [logoError, setLogoError] = useState(false);

  // Use PNG shield logo, fallback to SVG if error
  const logoSrc = logoError ? skeldirLogoSvg : skeldirLogoShield;

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
            src={logoSrc} 
            alt={isCollapsed ? "Skeldir" : ""} 
            aria-hidden={!isCollapsed}
            className="object-contain"
            style={{ width: '34px', height: '34px' }}
            onError={() => setLogoError(true)}
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
          className="flex items-center dashboard-logo"
          style={{
            filter: 'var(--dash-logo-glow)',
            transition: 'filter 300ms ease'
          }}
        >
          <img 
            src={logoSrc} 
            alt={!isCollapsed ? "Skeldir Logo" : ""} 
            aria-hidden={isCollapsed}
            className="h-12 w-auto object-contain"
            onError={() => setLogoError(true)}
          />
        </div>
      </div>
    </div>
  );
}