import type { LucideIcon } from 'lucide-react';
import { CheckCircle, AlertTriangle, AlertCircle, Info } from 'lucide-react';

type BadgeVariant = 'verified' | 'warning' | 'error' | 'info';

interface ReconciliationStatusBadgeProps {
  variant: BadgeVariant;
  showIcon?: boolean;
  children: React.ReactNode;
  className?: string;
  'data-testid'?: string;
}

const variantConfig: Record<BadgeVariant, { styles: string; icon: LucideIcon }> = {
  verified: {
    styles: 'bg-green-100 dark:bg-green-950/30 text-green-800 dark:text-green-400 border-green-300 dark:border-green-700',
    icon: CheckCircle,
  },
  warning: {
    styles: 'bg-amber-100 dark:bg-amber-950/30 text-amber-800 dark:text-amber-400 border-amber-300 dark:border-amber-700',
    icon: AlertTriangle,
  },
  error: {
    styles: 'bg-red-100 dark:bg-red-950/30 text-red-800 dark:text-red-400 border-red-300 dark:border-red-700',
    icon: AlertCircle,
  },
  info: {
    styles: 'bg-blue-100 dark:bg-blue-950/30 text-blue-800 dark:text-blue-400 border-blue-300 dark:border-blue-700',
    icon: Info,
  },
};

export function ReconciliationStatusBadge({
  variant,
  showIcon = false,
  children,
  className = '',
  'data-testid': dataTestId,
}: ReconciliationStatusBadgeProps) {
  const { styles, icon: Icon } = variantConfig[variant];
  
  // Use reconciliation-status-badge class for 20px typography per FE-UX-034
  // NOTE: text-sm removed to allow CSS to set 20px font size
  const baseStyles = 'reconciliation-status-badge inline-flex items-center px-3 py-1.5 rounded-full font-semibold border';

  return (
    <span 
      className={`${baseStyles} ${styles} ${className}`}
      role="status"
      aria-live="polite"
      data-testid={dataTestId || `badge-${variant}`}
    >
      {showIcon && <Icon className="w-5 h-5 mr-1.5" aria-hidden="true" />}
      {children}
    </span>
  );
}
