"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { BusinessEmailInput } from './BusinessEmailInput';
import { GoogleOAuthButton } from './GoogleOAuthButton';
import { MicrosoftOAuthButton } from './MicrosoftOAuthButton';
import { ArrowRight, Loader2 } from 'lucide-react';

export function SignUpForm() {
    const router = useRouter();
    const [email, setEmail] = useState('');
    const [isValid, setIsValid] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);

    const handleValidationChange = (valid: boolean, value: string) => {
        setIsValid(valid);
        setEmail(value);
        // Clear submit error when user modifies input
        if (submitError) setSubmitError(null);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!isValid || !email) return;

        setIsLoading(true);
        setSubmitError(null);

        try {
            // API Integration
            const response = await fetch('/api/v1/auth/signup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email,
                    source: 'direct_signup',
                    timestamp: new Date().toISOString(),
                }),
            });

            if (response.ok) {
                // Success: Redirect to onboarding
                const data = await response.json();
                window.location.href = data.redirectUrl || '/onboarding';
            } else {
                // Handle errors
                const errorData = await response.json();

                if (response.status === 429) {
                    setSubmitError("Too many attempts. Please try again in 60 seconds.");
                } else if (response.status === 422) {
                    setSubmitError(errorData.message || "Invalid email address.");
                } else {
                    setSubmitError("Something went wrong. Please try again.");
                }
            }
        } catch (error) {
            setSubmitError("Network error. Please check your connection.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="w-full max-w-md space-y-8">
            <div className="space-y-2 auth-form-header" style={{ textAlign: 'left' }}>
                <h1 className="tracking-tight auth-form-title" style={{ color: 'var(--color-black, #000000)', fontWeight: 600, whiteSpace: 'nowrap', fontSize: '2.75rem', lineHeight: 1.2, margin: 0, padding: 0 }}>
                    Get started with Skeldir
                </h1>
                <p className="text-base auth-form-subtitle" style={{ color: 'var(--color-black, #000000)', fontWeight: 400, lineHeight: 1.5, margin: 0, padding: 0 }}>
                    Know where your ad dollars actually go
                </p>
            </div>

            <div className="space-y-6">
                <form onSubmit={handleSubmit} className="space-y-4">
                    <BusinessEmailInput
                        onValidationChange={handleValidationChange}
                        disabled={isLoading}
                    />

                    {submitError && (
                        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                            {submitError}
                        </div>
                    )}

                    <Button
                        type="button"
                        onClick={() => router.push('/book-demo')}
                        disabled={!isValid || isLoading}
                        className="w-full h-12 text-white font-semibold transition-all duration-300 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                            backgroundColor: isValid && !isLoading ? '#2563EB' : '#9CA3AF',
                            boxShadow: isValid && !isLoading 
                                ? '0 4px 14px rgba(37, 99, 235, 0.35), 0 0 0 0 rgba(37, 99, 235, 0)' 
                                : 'none',
                            transform: isValid && !isLoading ? 'scale(1)' : 'scale(0.98)',
                            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                        }}
                        onMouseEnter={(e) => {
                            if (isValid && !isLoading) {
                                e.currentTarget.style.backgroundColor = '#1D4ED8';
                                e.currentTarget.style.transform = 'translateY(-2px) scale(1.02)';
                                e.currentTarget.style.boxShadow = '0 8px 20px rgba(37, 99, 235, 0.45)';
                            }
                        }}
                        onMouseLeave={(e) => {
                            if (isValid && !isLoading) {
                                e.currentTarget.style.backgroundColor = '#2563EB';
                                e.currentTarget.style.transform = 'scale(1)';
                                e.currentTarget.style.boxShadow = '0 4px 14px rgba(37, 99, 235, 0.35)';
                            }
                        }}
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Creating account...
                            </>
                        ) : (
                            <>
                                Get Started
                                <ArrowRight className="ml-2 h-4 w-4 transition-transform duration-300" style={{ transform: isValid ? 'translateX(0)' : 'translateX(-4px)' }} />
                            </>
                        )}
                    </Button>
                </form>

                <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                        <span className="w-full border-t border-gray-700" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase text-white">
                        <span className="bg-white px-2 text-gray-500">
                            Or continue with
                        </span>
                    </div>
                </div>

                <div className="space-y-3">
                    <GoogleOAuthButton disabled={isLoading} />
                    <MicrosoftOAuthButton disabled={isLoading} />
                </div>
            </div>

            <style dangerouslySetInnerHTML={{__html: `
                @media (max-width: 767px) {
                    .auth-form-header {
                        width: 100% !important;
                        max-width: 100% !important;
                    }

                    .auth-form-title {
                        white-space: normal !important;
                        font-size: 32px !important;
                        line-height: 1.25 !important;
                        word-wrap: break-word !important;
                        overflow-wrap: break-word !important;
                    }

                    .auth-form-subtitle {
                        font-size: 15px !important;
                        line-height: 1.5 !important;
                    }
                }
            `}} />
        </div>
    );
}
