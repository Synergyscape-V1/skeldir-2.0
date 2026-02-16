/**
 * Header Logo Component — Always Visible, Resizable
 * 
 * Professional logo display in header area, independent of sidebar state.
 * Supports resizing and maintains visibility regardless of navigation collapse state.
 */

import { useState } from "react";
import skeldirLogoShield from "@assets/brand/logo-shield.png";
import skeldirLogoSvg from "@assets/brand/logo.svg";
import { cn } from "@/lib/utils";

interface HeaderLogoProps {
  /** Size variant: 'sm' (compact), 'md' (default), 'lg' (prominent) */
  size?: "sm" | "md" | "lg";
  /** Additional className for styling */
  className?: string;
}

export function HeaderLogo({ size = "md", className }: HeaderLogoProps) {
  const [logoError, setLogoError] = useState(false);

  // Use PNG shield logo, fallback to SVG if error
  const logoSrc = logoError ? skeldirLogoSvg : skeldirLogoShield;

  const sizeClasses = {
    sm: "h-6 w-auto",
    md: "h-8 w-auto",
    lg: "h-10 w-auto",
  };

  return (
    <div
      className={cn(
        "flex items-center justify-center transition-opacity duration-200 hover:opacity-80",
        className
      )}
      data-testid="header-logo"
    >
      <div
        className="flex items-center dashboard-logo"
        style={{
          filter: "var(--dash-logo-glow)",
          transition: "filter 300ms ease",
        }}
      >
        <img
          src={logoSrc}
          alt="Skeldir Logo"
          className={cn(
            "object-contain transition-all duration-200",
            sizeClasses[size]
          )}
          onError={() => setLogoError(true)}
        />
      </div>
    </div>
  );
}
