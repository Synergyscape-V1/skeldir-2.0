/** TikTok platform logo — monochrome SVG, theme-safe via currentColor */
interface Props { className?: string; size?: number; }
export function TikTokLogo({ className, size = 20 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.3 0 .59.05.86.13V9.01a6.32 6.32 0 0 0-.86-.06 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.34-6.34V8.76a8.2 8.2 0 0 0 4.78 1.53V6.84a4.86 4.86 0 0 1-1.02-.15z"
        fill="currentColor"
      />
    </svg>
  );
}
