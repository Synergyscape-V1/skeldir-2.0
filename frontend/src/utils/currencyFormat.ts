/**
 * Format number as USD currency with proper locale formatting
 * @param amount - Dollar amount to format
 * @param options - Intl.NumberFormat options
 * @returns Formatted currency string (e.g., "$9,483.77")
 */
export const formatCurrency = (
  amount: number,
  options?: Intl.NumberFormatOptions
): string => {
  const defaultOptions: Intl.NumberFormatOptions = {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  };

  return new Intl.NumberFormat('en-US', {
    ...defaultOptions,
    ...options,
  }).format(amount);
};

/**
 * Format number as compact currency (e.g., "$9.5K", "$1.2M")
 * @param amount - Dollar amount to format
 * @returns Compact formatted string
 */
export const formatCompactCurrency = (amount: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(amount);
};
