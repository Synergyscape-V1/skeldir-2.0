"use client";

import React from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface MicrosoftOAuthButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    className?: string;
}

export function MicrosoftOAuthButton({ className, ...props }: MicrosoftOAuthButtonProps) {
    const router = useRouter();

    const handleClick = () => {
        router.push('/book-demo');
    };

    return (
        <Button
            type="button"
            variant="outline"
            className={cn(
                "w-full h-12 bg-white hover:bg-gray-50 text-gray-900 border-gray-300 hover:border-gray-400 transition-all font-medium flex items-center justify-center gap-2",
                className
            )}
            onClick={handleClick}
            {...props}
        >
            <svg className="h-5 w-5" viewBox="0 0 23 23" fill="none">
                <path fill="#F25022" d="M0 0h11v11H0z" />
                <path fill="#00A4EF" d="M12 0h11v11H12z" />
                <path fill="#7FBA00" d="M0 12h11v11H0z" />
                <path fill="#FFB900" d="M12 12h11v11H12z" />
            </svg>
            Continue with Microsoft
        </Button>
    );
}
