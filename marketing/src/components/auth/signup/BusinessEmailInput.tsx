"use client";

import React, { useState, useEffect, forwardRef } from 'react';
import { validateBusinessEmail } from '@/lib/validation/emailValidator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

interface BusinessEmailInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    onValidationChange: (isValid: boolean, value: string) => void;
    className?: string;
}

export const BusinessEmailInput = forwardRef<HTMLInputElement, BusinessEmailInputProps>(
    ({ className, onValidationChange, ...props }, ref) => {
        const [value, setValue] = useState('');
        const [error, setError] = useState<string | null>(null);
        const [isTouched, setIsTouched] = useState(false);
        const [isValid, setIsValid] = useState(false);

        const validate = (email: string) => {
            const result = validateBusinessEmail(email);
            const valid = result.isValid;

            setIsValid(valid);
            setError(result.error || null);
            onValidationChange(valid, email);

            return valid;
        };

        const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            const newValue = e.target.value;
            setValue(newValue);

            // Real-time validation - validate as user types for better UX
            // This allows the button to enable/disable smoothly as user types
            if (newValue.length > 0) {
                validate(newValue);
            } else {
                // Clear validation state when input is empty
                setIsValid(false);
                setError(null);
                onValidationChange(false, '');
            }
        };

        const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
            setIsTouched(true);
            validate(e.target.value);
            if (props.onBlur) props.onBlur(e);
        };

        return (
            <div className={cn("space-y-2", className)}>
                <Label htmlFor="email" className="text-sm font-medium" style={{ color: 'var(--color-black, #000000)' }}>
                    Work Email
                </Label>
                <div className="relative">
                    <Input
                        ref={ref}
                        id="email"
                        type="email"
                        placeholder="What's your work email?"
                        className={cn(
                            "h-12 placeholder:text-gray-400 focus:border-blue-500 focus:ring-blue-500/20 transition-all",
                            error && "border-red-500 focus:border-red-500 focus:ring-red-500/20",
                            isValid && isTouched && !error && "border-green-500/50 focus:border-green-500 focus:ring-green-500/20"
                        )}
                        style={{ 
                            color: '#000000',
                            backgroundColor: '#FFFFFF',
                            border: '1px solid rgba(0, 0, 0, 0.2)',
                        }}
                        value={value}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        autoComplete="email"
                        {...props}
                    />

                    {/* Status Icons */}
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                        {error && <AlertCircle className="h-5 w-5 text-red-500" />}
                        {isValid && isTouched && !error && <CheckCircle2 className="h-5 w-5 text-green-500" />}
                    </div>
                </div>

                {/* Error Message */}
                {error && (
                    <p className="text-sm text-red-400 animate-in slide-in-from-top-1 fade-in duration-200" role="alert">
                        {error}
                    </p>
                )}
            </div>
        );
    }
);

BusinessEmailInput.displayName = "BusinessEmailInput";
