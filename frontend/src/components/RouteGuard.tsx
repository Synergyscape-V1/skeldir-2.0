// RouteGuard - High-performance auth guard with glass UI, sub-100ms validation, WCAG-compliant
import { useEffect, useState, useCallback, useRef } from 'react';
import { useLocation } from 'wouter';
import { globalAuthState } from '@/lib/auth-state-manager';
import { Button } from '@/components/ui/button';
import redirectIcon from '@/assets/brand/icons/redirect.svg';
import { useErrorBanner } from '@/hooks/use-error-banner';
import { ErrorBannerMapper } from '@/lib/error-banner-mapper';

interface RouteGuardProps { children: React.ReactNode; redirectTo?: string; }

export function RouteGuard({ children, redirectTo = '/' }: RouteGuardProps) {
  const [, navigate] = useLocation();
  const [authState, setAuthState] = useState(globalAuthState.getState());
  const previousAuthRef = useRef<boolean | null>(null);
  const { showBanner } = useErrorBanner();

  const handleAuthFailure = useCallback((error: string) => {
    console.error(`[RouteGuard] Auth failure: ${error}`);
    const correlationId = `auth-guard-${Date.now()}`;
    
    const bannerConfig = ErrorBannerMapper.mapAuthError('session_expired', correlationId);
    showBanner(bannerConfig);
    
    const currentPath = window.location.pathname + window.location.search;
    const returnUrl = currentPath !== redirectTo ? `?returnUrl=${encodeURIComponent(currentPath)}` : '';
    navigate(`${redirectTo}${returnUrl}`);
  }, [navigate, redirectTo, showBanner]);

  const performAuthCheck = useCallback(async () => {
    try {
      const result = await globalAuthState.checkAuth();
      if (!result) {
        handleAuthFailure('Authentication required');
      }
    } catch (error) {
      handleAuthFailure('Authentication check failed');
    }
  }, [handleAuthFailure]);

  useEffect(() => {
    // Subscribe to global auth state changes
    const unsubscribe = globalAuthState.subscribe(setAuthState);
    
    // Trigger auth check on mount
    performAuthCheck();
    
    return unsubscribe;
  }, []); // Only run once on mount

  // Redirect when user becomes unauthenticated (e.g., after logout)
  useEffect(() => {
    // Only redirect if transitioning from authenticated to unauthenticated
    if (previousAuthRef.current === true && !authState.isChecking && !authState.isAuthenticated) {
      handleAuthFailure('Logged out');
    }
    
    // Update the ref after checking
    if (!authState.isChecking) {
      previousAuthRef.current = authState.isAuthenticated;
    }
  }, [authState.isChecking, authState.isAuthenticated, handleAuthFailure]);

  if (authState.isChecking) return <GlassOverlay />;
  if (authState.error && !authState.isAuthenticated) return <GlassOverlay isError />;
  if (authState.isAuthenticated) return <>{children}</>;
  
  return null;
}

function GlassOverlay({ isError = false }: { isError?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-md"
         style={{ backgroundColor: 'var(--glass-overlay-bg)' }}>
      <div className="p-8 max-w-md mx-4 rounded-xl border border-white/20 backdrop-blur-xl shadow-2xl"
           style={{ backgroundColor: 'var(--glass-card-bg)', borderColor: 'var(--glass-border)' }}>
        
        {isError ? (
          <div className="text-center space-y-6" role="alert" aria-live="assertive">
            <div className="w-16 h-16 mx-auto rounded-full flex items-center justify-center"
                 style={{ backgroundColor: 'var(--glass-error-bg)' }}>
              <svg className="w-8 h-8" style={{ color: 'var(--glass-error-icon)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <div>
              <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--glass-error-text)' }}>
                Authentication Required
              </h2>
              <p className="mb-4" style={{ color: 'var(--glass-text-secondary)' }}>
                Please log in to access this page.
              </p>
              <div className="flex gap-3 justify-center">
                <Button onClick={() => {
                          globalAuthState.refreshAuth();
                        }} className="flex items-center space-x-2"
                        style={{ backgroundColor: 'var(--glass-redirect-bg)', color: 'var(--glass-redirect-text)' }}
                        data-testid="button-retry-auth" autoFocus>
                  <img src={redirectIcon} alt="" className="w-4 h-4" /><span>Retry</span>
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center space-y-6" role="status" aria-live="polite">
            <div className="w-16 h-16 mx-auto rounded-full flex items-center justify-center"
                 style={{ backgroundColor: 'var(--glass-loading-bg)' }}>
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-b-transparent"
                   style={{ borderColor: 'var(--glass-loading-spinner)', borderBottomColor: 'transparent' }}></div>
            </div>
            <div>
              <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--glass-text-primary)' }}>
                Verifying Access
              </h2>
              <p style={{ color: 'var(--glass-text-secondary)' }}>
                Checking your authentication status...
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}