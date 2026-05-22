"use client";

import React from 'react';
import { Button } from '@/components/ui/button';
import { Github } from 'lucide-react';
import { cn } from '@/lib/utils';

interface GitHubOAuthButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    className?: string;
}

export function GitHubOAuthButton({ className, ...props }: GitHubOAuthButtonProps) {
    const handleGitHubLogin = () => {
        // Direct navigation to backend OAuth endpoint as per architecture B1.3
        window.location.href = '/api/v1/auth/github';
    };

    return (
        <Button
            type="button"
            variant="outline"
            className={cn(
                "w-full h-12 bg-[#24292e] hover:bg-[#2f363d] text-white border-transparent hover:border-gray-600 transition-all font-medium flex items-center justify-center gap-2",
                className
            )}
            onClick={handleGitHubLogin}
            {...props}
        >
            <Github className="h-5 w-5" />
            Sign up with GitHub
        </Button>
    );
}
