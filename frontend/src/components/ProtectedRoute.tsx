/**
 * Protected Route component for authentication-required pages
 */

import { useAuth } from '@/hooks/useAuth';
import { useLocation } from 'wouter';
import { useEffect } from 'react';

interface ProtectedRouteProps {
  children: React.ReactNode;
  redirectTo?: string;
  requireAuth?: boolean;
}

/**
 * Component that protects routes requiring authentication
 */
export function ProtectedRoute({ 
  children, 
  redirectTo = '/', 
  requireAuth = true 
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const [, navigate] = useLocation();

  useEffect(() => {
    if (!isLoading) {
      if (requireAuth && !isAuthenticated) {
        navigate(redirectTo);
      }
    }
  }, [isAuthenticated, isLoading, requireAuth, redirectTo, navigate]);

  // Show loading while checking authentication
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen" data-testid="loading-auth">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  // Don't render children if auth check failed
  if (requireAuth && !isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}

/**
 * Hook for conditional rendering based on auth status
 */
export function useAuthGuard() {
  const { isAuthenticated, isLoading, user } = useAuth();

  return {
    isAuthenticated,
    isLoading,
    user,
    canAccess: (requireAuth: boolean = true) => {
      if (isLoading) return false;
      return requireAuth ? isAuthenticated : true;
    },
  };
}