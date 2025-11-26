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
    
    // Update both auth state systems
    globalAuthState = { user: tokens.user, isAuthenticated: true, isLoading: false };
    authStateListeners.forEach(listener => listener());
    
    // Force auth state manager to refresh and recognize the login
    await authStateManager.refreshAuth();
    
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

  const performLogin = useCallback(async (email: string, password: string, rememberMe: boolean = false) => {
    setIsLoading(true);
    setError(null);

    try {
      const { authClient } = await import('@/api/auth-client');
      const response = await authClient.login({ email, password });

      if (response.error) {
        const errorMessage = response.error.detail || 'Login failed';
        setError(errorMessage);
        setIsLoading(false);
        return { success: false, user: null };
      }
      
      if (response.data) {
        const tokens = {
          token: response.data.access_token,
          user: {
            id: email,
            email,
            name: email.split('@')[0],
          },
        };
        await login(tokens);
        setIsLoading(false);
        return { success: true, user: tokens.user };
      } else {
        setError('Invalid login response');
        setIsLoading(false);
        return { success: false, user: null };
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message || 'Login failed');
      } else {
        setError('Login failed');
      }
      setIsLoading(false);
      return { success: false, user: null };
    }
  }, [login]);

  return {
    login: performLogin,
    isLoading,
    error,
    clearError: () => setError(null),
  };
}