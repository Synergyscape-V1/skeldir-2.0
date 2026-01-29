/**
 * Email validation utility for business email addresses
 */

export interface ValidationResult {
  isValid: boolean;
  error: string | null;
}

export function validateBusinessEmail(email: string): ValidationResult {
  // Basic email format validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return {
      isValid: false,
      error: 'Please enter a valid email address'
    };
  }

  // List of common free email providers to reject
  const freeEmailProviders = [
    'gmail.com',
    'yahoo.com',
    'hotmail.com',
    'outlook.com',
    'aol.com',
    'icloud.com',
    'mail.com',
    'protonmail.com',
  ];

  const domain = email.split('@')[1]?.toLowerCase();
  
  // Reject free email providers
  if (freeEmailProviders.includes(domain)) {
    return {
      isValid: false,
      error: 'Please use a business email address'
    };
  }

  return {
    isValid: true,
    error: null
  };
}

export function getEmailDomain(email: string): string | null {
  const parts = email.split('@');
  return parts.length === 2 ? parts[1].toLowerCase() : null;
}
