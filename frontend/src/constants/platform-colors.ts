/**
 * Platform Card Color Constants
 * 
 * FE-UX-016: Data Integrity Monitor Color-Coded Top Borders
 * 
 * These colors match FE-UX-015 (Revenue Overview) for visual consistency:
 * - Verified platforms: Green top border
 * - Unverified/Partial/Pending platforms: Amber top border
 * 
 * Source: client/src/index.css lines 82-86, 206-210
 */

/**
 * CSS Custom Property References
 * These map to the revenue verification colors defined in index.css
 */
export const PLATFORM_BORDER_COLORS = {
  /**
   * Verified platform border color (Green)
   * Light mode: hsl(160 84% 39%)
   * Dark mode: hsl(160 84% 45%)
   * Usage: Tailwind class or CSS var(--verified)
   */
  VERIFIED: 'hsl(var(--verified) / 1)',
  
  /**
   * Unverified/Partial/Pending platform border color (Amber)
   * Light mode: hsl(38 92% 50%)
   * Dark mode: hsl(38 92% 55%)
   * Usage: Tailwind class or CSS var(--unverified)
   */
  UNVERIFIED: 'hsl(var(--unverified) / 1)',
} as const;

/**
 * Tailwind Border Width
 * FE-UX-016 specifies 3px top border for platform cards
 */
export const PLATFORM_BORDER_WIDTH = '3px';

/**
 * Helper function to determine border color based on platform status
 */
export function getPlatformBorderColor(
  status: 'verified' | 'partial' | 'pending' | 'error' | 'unverified'
): string {
  return status === 'verified' 
    ? PLATFORM_BORDER_COLORS.VERIFIED 
    : PLATFORM_BORDER_COLORS.UNVERIFIED;
}

/**
 * Tailwind class helper for border styling
 * Returns the appropriate Tailwind border classes
 */
export function getPlatformBorderClasses(
  status: 'verified' | 'partial' | 'pending' | 'error' | 'unverified'
): string {
  const borderClass = status === 'verified' ? 'border-t-[#16A34A]' : 'border-t-[#F59E0B]';
  return `border-t-[3px] ${borderClass}`;
}
