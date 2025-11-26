/**
 * ProfessionalUtilityButton Component
 * 
 * Design System Pattern: Clean, Flat Design for Professional B2B/Enterprise UI
 * 
 * Visual Hierarchy Strategy:
 * - All navigation and utility actions use consistent flat design
 * - Clear borders and backgrounds for trust and clarity
 * - Subtle hover states without playful transforms
 * 
 * Professional Properties:
 * - Solid backgrounds with proper contrast
 * - Clear borders for definition
 * - Minimal hover states for professional feel
 * - Rectangular shapes (4px radius) for enterprise aesthetic
 */

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";
import { Loader2, LucideIcon } from "lucide-react";

export interface GlassmorphicUtilityButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Lucide icon component to display */
  icon: LucideIcon;
  /** Text label for expanded state */
  label: string;
  /** Whether the sidebar is collapsed (icon-only mode) */
  isCollapsed?: boolean;
  /** Loading state for async actions */
  isLoading?: boolean;
  /** Custom loading text */
  loadingText?: string;
  /** Whether to render as child component */
  asChild?: boolean;
}

const GlassmorphicUtilityButton = React.forwardRef<HTMLButtonElement, GlassmorphicUtilityButtonProps>(
  ({ 
    className, 
    icon: Icon, 
    label, 
    isCollapsed = false, 
    isLoading = false,
    loadingText,
    asChild = false,
    disabled,
    ...props 
  }, ref) => {
    const Comp = asChild ? Slot : "button";
    
    return (
      <Comp
        ref={ref}
        disabled={disabled || isLoading}
        aria-label={isLoading ? loadingText || `Loading ${label}` : label}
        aria-live={isLoading ? "polite" : undefined}
        className={cn(
          // Base professional flat styles
          "relative inline-flex items-center justify-center gap-2",
          "font-medium transition-colors duration-150 ease-out",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
          
          // Professional flat design - solid backgrounds
          "bg-sidebar-accent text-sidebar-accent-foreground",
          "border border-sidebar-border",
          "shadow-sm",
          
          // Subtle professional hover state - no transforms
          "hover-elevate active-elevate-2",
          
          // Disabled state
          "disabled:opacity-50 disabled:cursor-not-allowed",
          
          // Collapsed vs Expanded layout - both rectangular
          isCollapsed 
            ? "h-9 w-9 rounded-md p-0" // Square icon-only with minimal radius
            : "min-h-10 w-full rounded-md px-3 py-2 text-sm justify-start", // Full-width with label
          
          className
        )}
        {...props}
      >
        {isLoading ? (
          <>
            <Loader2 className={cn(
              "animate-spin",
              isCollapsed ? "h-5 w-5" : "h-4 w-4"
            )} />
            {!isCollapsed && loadingText && (
              <span className="truncate">{loadingText}</span>
            )}
            {/* Screen reader only text for collapsed loading state */}
            {isCollapsed && loadingText && (
              <span className="sr-only">{loadingText}</span>
            )}
          </>
        ) : (
          <>
            <Icon className={cn(
              isCollapsed ? "h-5 w-5" : "h-4 w-4",
              "shrink-0"
            )} />
            {!isCollapsed && (
              <span className="truncate">{label}</span>
            )}
            {/* Screen reader only text for collapsed state */}
            {isCollapsed && (
              <span className="sr-only">{label}</span>
            )}
          </>
        )}
      </Comp>
    );
  }
);

GlassmorphicUtilityButton.displayName = "GlassmorphicUtilityButton";

export { GlassmorphicUtilityButton };
