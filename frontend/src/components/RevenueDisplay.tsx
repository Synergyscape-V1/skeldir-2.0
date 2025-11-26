import { formatCurrency } from '@/lib/currency-utils';
import { useAnimatedValue } from '@/hooks/use-animated-value';
import checkmarkIcon from '@/assets/brand/icons/checkmark.svg';

interface RevenueDisplayProps {
  value: number;
  currency: 'USD' | 'EUR';
  verified: boolean;
}

export default function RevenueDisplay({ value, currency, verified }: RevenueDisplayProps) {
  const animatedValue = useAnimatedValue(value);
  const formattedValue = formatCurrency(animatedValue, currency, true);
  const isNegative = value < 0;

  return (
    <div 
      className="revenue-card relative p-5 rounded-xl border overflow-visible min-w-[280px]" 
      style={{ borderColor: 'var(--revenue-border)', boxShadow: '0 4px 24px rgba(70, 139, 230, 0.1)' }} 
      role="status" 
      aria-live="polite" 
      aria-label={`Revenue: ${formattedValue}, ${verified ? 'verified' : 'unverified'}`} 
      data-testid="revenue-display"
    >
      {verified && (
        <div 
          className="verification-checkmark absolute -top-2 -right-2 w-10 h-10 rounded-full flex items-center justify-center z-10" 
          style={{ backgroundColor: 'var(--revenue-verified-bg)', boxShadow: '0 2px 8px rgba(70, 139, 230, 0.2)' }} 
          data-testid="badge-verified"
        >
          <img src={checkmarkIcon} alt="Verified" className="w-5 h-5" />
        </div>
      )}
      <div 
        className="revenue-value overflow-hidden text-2xl md:text-[28px] lg:text-4xl" 
        style={{ 
          color: isNegative ? 'var(--revenue-negative)' : 'var(--revenue-text)', 
          fontWeight: 700, 
          letterSpacing: '-0.02em',
          whiteSpace: 'nowrap',
          textOverflow: 'ellipsis'
        }} 
        title={formattedValue}
        data-testid="text-revenue-value"
      >
        {formattedValue}
      </div>
    </div>
  );
}
