import { useId } from 'react';
import { AUTH_COPY } from '../../../auth/copy';
import { validateBusinessEmail } from '../../../auth/businessEmail';
import { FormField } from '../../form/FormField/FormField';

export interface BusinessEmailInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  showValidation?: boolean;
  id?: string;
}

export function getBusinessEmailError(raw: string, showValidation: boolean): string | undefined {
  if (!showValidation) return undefined;
  const result = validateBusinessEmail(raw);
  if (result.ok) return undefined;
  if (result.reason === 'empty') return 'Enter your work email.';
  if (result.reason === 'invalid_format') return 'Enter a valid email address.';
  return AUTH_COPY.emailNotBusiness;
}

export function BusinessEmailInput({
  value,
  onChange,
  disabled,
  showValidation = false,
  id,
}: BusinessEmailInputProps) {
  const autoId = useId();
  const fieldId = id ?? `business-email-${autoId}`;
  const error = getBusinessEmailError(value, showValidation);

  return (
    <FormField
      id={fieldId}
      label={AUTH_COPY.emailLabel}
      type="email"
      autoComplete="email"
      inputMode="email"
      value={value}
      onChange={(event: React.ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
      disabled={disabled}
      error={error}
      hint="Use your company domain email."
    />
  );
}
