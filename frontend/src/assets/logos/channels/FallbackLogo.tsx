/** Fallback channel logo — generic link glyph for unknown platforms */
import { Link2 } from 'lucide-react';

interface Props { className?: string; size?: number; }
export function FallbackLogo({ className, size = 20 }: Props) {
  return <Link2 className={className} width={size} height={size} aria-hidden="true" />;
}
