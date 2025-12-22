/**
 * Authentication hooks for React components
 */

import { useState, useEffect, useCallback } from 'react';
import { authUtils, type AuthUser, type AuthTokens } from '@/lib/auth';
import { globalAuthState as authStateManager } from '@/lib/auth-state-manager';

export interface UseAuthReturn {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (tokens: AuthTokens) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

// Global auth state to prevent multiple simultaneous checks
let globalAuthState: { user: AuthUser | null; isAuthenticated: boolean; isLoading: boolean } | null = null;
let authCheckPromise: Promise<void> | null = null;
const authStateListeners: Set<() => void> = new Set();

/**
 * Main authentication hook with debounced state management
 */
export function useAuth(): UseAuthReturn {
  const [authState, setAuthState] = useState(() => {
    // Initialize global state if not already set
    if (!globalAuthState) {
      globalAuthState = { user: null, isAuthenticated: false, isLoading: true };
    }
    return { ...globalAuthState };
  });

  // Subscribe to global auth state changes
  useEffect(() => {
    const listener = () => {
      if (globalAuthState) {
        setAuthState({ ...globalAuthState });
      }
    };
    
    authStateListeners.add(listener);
    
    return () => {
      authStateListeners.delete(listener);
    };
  }, []);

  // Debounced auth check that prevents concurrent executions
  const checkAuth = useCallback(async () => {
    // If already checking, wait for that check to complete
    if (authCheckPromise) {
      return authCheckPromise;
    }
    
    authCheckPromise = (async () => {
      try {
        // Update global loading state
        const currentState = globalAuthState || { user: null, isAuthenticated: false, isLoading: false };
        globalAuthState = { ...currentState, isLoading: true };
        authStateListeners.forEach(listener => listener());
        
        const isAuth = authUtils.isAuthenticated();
        const currentUser = authUtils.getCurrentUser();
        
        // If we think we're authenticated but have no user, try a quick sync
        if (isAuth && !currentUser) {
          try {
            await Promise.race([
              authUtils.syncAuthState(),
              new Promise<void>((_, reject) => 
                setTimeout(() => reject(new Error('Auth sync timed out')), 3000) // Reduced timeout
              ),
            ]);
            
            const syncedUser = authUtils.getCurrentUser();
            if (syncedUser) {
              globalAuthState = { user: syncedUser, isAuthenticated: true, isLoading: false };
            } else {
              console.warn('Sync failed to recover user data, clearing auth state');
              globalAuthState = { user: null, isAuthenticated: false, isLoading: false };
            }
          } catch (error) {
            console.warn('Auth sync failed, using cached state:', error);
            globalAuthState = { user: null, isAuthenticated: false, isLoading: false };
          }
        } else {
          globalAuthState = { 
            user: isAuth ? currentUser : null, 
            isAuthenticated: isAuth, 
            isLoading: false 
          };
        }
        
        // Notify all listeners
        authStateListeners.forEach(listener => listener());
      } catch (error) {
        console.error('Auth check failed:', error);
        globalAuthState = { user: null, isAuthenticated: false, isLoading: false };
        authStateListeners.forEach(listener => listener());
      } finally {
        authCheckPromise = null;
      }
    })();
    
    return authCheckPromise;
  }, []);

  // Optimized login function
  const login = useCallback(async (tokens: AuthTokens) => {
    // Wait for storage operations to complete
    await authUtils.login(tokens);
    
    // Update both auth state systems synchronously to prevent race conditions
    globalAuthState = { user: tokens.user, isAuthenticated: true, isLoading: false };
    authStateListeners.forEach(listener => listener());
    
    // Immediately mark as authenticated in the global state manager (used by RouteGuard)
    // This bypasses async checks to prevent race conditions during navigation
    authStateManager.markAuthenticated();
    
    // Sync in background without blocking UI
    authUtils.syncAuthState().catch(error => {
      console.error('Background auth sync after login failed:', error);
    });
  }, []);

  // Optimized logout function
  const logout = useCallback(() => {
    authUtils.logout();
    
    // Update both auth state systems
    globalAuthState = { user: null, isAuthenticated: false, isLoading: false };
    authStateListeners.forEach(listener => listener());
    
    // Clear auth state manager
    authStateManager.clearAuth();
  }, []);

  // Check auth on mount only if not already checked
  useEffect(() => {
    if (!globalAuthState || globalAuthState.isLoading) {
      checkAuth();
    }
  }, []); // Remove checkAuth dependency to prevent re-runs

  // Token expiration monitoring for this hook instance only
  useEffect(() => {
    if (!authState.isAuthenticated) return;

    const checkTokenExpiration = () => {
      if (authUtils.tokenExpiresWithin(1)) {
        console.warn('Token expired, logging out');
        logout();
      }
    };

    const interval = setInterval(checkTokenExpiration, 60000);
    
    return () => clearInterval(interval);
  }, [authState.isAuthenticated, logout]); // Keep dependencies for proper cleanup

  return {
    user: authState.user,
    isAuthenticated: authState.isAuthenticated,
    isLoading: authState.isLoading,
    login,
    logout,
    checkAuth,
  };
}

/**
 * Hook to check if user is authenticated (simple boolean)
 */
export function useIsAuthenticated(): boolean {
  const { isAuthenticated } = useAuth();
  return isAuthenticated;
}

/**
 * Hook to get current authenticated user
 */
export function useCurrentUser(): AuthUser | null {
  const { user } = useAuth();
  return user;
}

/**
 * Hook for login functionality with loading state
 */
export function useLogin() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { login } = useAuth();

  // Memoize clearError to prevent infinite effect loops in consumers
  const clearError = useCallback(() => setError(null), []);

  const performLogin = useCallback(async (email: string, password: string, rememberMe: boolean = false) => {
    setIsLoading(true);
    setError(null);

    try {
      // DEV MODE: If no backend is available, use mock authentication
      // This allows testing the UI flow without a running backend
      const useMockAuth = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_AUTH !== 'false';
      
      let responseData: {
        access_token: string;
        refresh_token: string;
        expires_in: number;
        token_type?: string;
        user?: { id: string; email: string; username: string };
      };

      if (useMockAuth) {
        // Mock authentication for development
        console.log('[useLogin] Using mock authentication (DEV mode)');
        await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay
        
        // Accept any email/password in dev mode
        responseData = {
          access_token: 'mock_access_token_' + Date.now(),
          refresh_token: 'mock_refresh_token_' + Date.now(),
          expires_in: 3600,
          token_type: 'Bearer',
          user: {
            id: 'mock-user-' + Date.now(),
            email: email,
            username: email.split('@')[0],
          },
        };
      } else {
        // Production: Use real API
        const { authService } = await import('@/api/services/auth-client');
        const response = await authService.login({ email, password });
        responseData = response.data as typeof responseData;
      }

      // B0.2 contract: login response REQUIRES access_token, refresh_token, expires_in
      // 'user' is optional - if not provided, we synthesize it from login email
      
      // Validate B0.2 required fields: access_token, refresh_token, expires_in
      // Surface explicit errors via UI state (consumed by toast in LoginInterface)
      if (!responseData.access_token) {
        const errorMsg = 'Authentication failed: missing access_token from server';
        console.error('[useLogin] B0.2 contract violation:', errorMsg);
        setError(errorMsg);
        setIsLoading(false);
        return { success: false, user: null };
      }
      if (!responseData.refresh_token) {
        const errorMsg = 'Authentication failed: missing refresh_token from server';
        console.error('[useLogin] B0.2 contract violation:', errorMsg);
        setError(errorMsg);
        setIsLoading(false);
        return { success: false, user: null };
      }
      if (responseData.expires_in === undefined || responseData.expires_in === null) {
        const errorMsg = 'Authentication failed: missing expires_in from server';
        console.error('[useLogin] B0.2 contract violation:', errorMsg);
        setError(errorMsg);
        setIsLoading(false);
        return { success: false, user: null };
      }
      
      // Use returned user if available, otherwise synthesize from login email
      const userFromResponse = responseData.user && responseData.user.id && responseData.user.email
        ? {
            id: responseData.user.id,
            email: responseData.user.email,
            username: responseData.user.username || responseData.user.email.split('@')[0],
            emailVerified: false,
          }
        : {
            id: crypto.randomUUID(),
            email: email,
            username: email.split('@')[0],
            emailVerified: false,
          };
      
      const tokens = {
        token: responseData.access_token,
        refreshToken: responseData.refresh_token,
        expiresIn: responseData.expires_in,
        user: userFromResponse,
      };
      await login(tokens);
      setIsLoading(false);
      return { success: true, user: userFromResponse };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed';
      console.error('[useLogin] Login error:', errorMessage, err);
      setError(errorMessage);
      setIsLoading(false);
      return { success: false, user: null };
    }
  }, [login]);

  return {
    login: performLogin,
    isLoading,
    error,
    clearError,
  };
}