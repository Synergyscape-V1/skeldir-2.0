import { CheckCircle2, AlertCircle, Loader2, Layers } from 'lucide-react';

interface StatusIconProps {
  type: 'high' | 'medium' | 'pending' | 'multiple';
  size?: number;
  ariaLabel: string;
}

export default function StatusIcon({ type, size = 32, ariaLabel }: StatusIconProps) {
  const sizeClass = size === 16 ? 'w-4 h-4' : 'w-8 h-8';
  
  const iconMap = {
    high: {
      Icon: CheckCircle2,
      color: '#059669',
      className: sizeClass,
    },
    medium: {
      Icon: AlertCircle,
      color: '#B45309',
      className: sizeClass,
    },
    pending: {
      Icon: Loader2,
      color: '#3B82F6',
      className: `${sizeClass} animate-spin`,
    },
    multiple: {
      Icon: Layers,
      color: '#8B5CF6',
      className: sizeClass,
    },
  };

  const { Icon, color, className } = iconMap[type];

  return (
    <Icon
      className={className}
      style={{ color }}
      role="img"
      aria-label={ariaLabel}
      data-testid={`status-icon-${type}`}
    />
  );
}
