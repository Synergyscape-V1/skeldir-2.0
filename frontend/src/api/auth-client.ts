/**
 * Authentication Client Compatibility Layer
 * Provides backward-compatible auth client interface
 */

import { authService } from './services/auth-client';
import { ApiError } from '@/lib/rfc7807-handler';

/**
 * Legacy-compatible auth client
 * Wraps the new authService to maintain backward compatibility
 * B0.2: Uses auth.yaml contract endpoints
 */
export const authClient = {
  async login(credentials: { email: string; password: string }) {
    try {
      const response = await authService.login({
        email: credentials.email,
        password: credentials.password,
      });

      return {
        data: response.data,
        error: null,
        correlationId: response.correlationId,
      };
    } catch (error) {
      if (error instanceof ApiError) {
        return {
          data: null,
          error: {
            detail: error.getUserMessage(),
            status: error.problem.status,
          },
          correlationId: error.correlationId,
        };
      }

      return {
        data: null,
        error: {
          detail: error instanceof Error ? error.message : 'Login failed',
          status: 500,
        },
        correlationId: undefined,
      };
    }
  },

  async refresh(refreshToken: string) {
    try {
      const response = await authService.refresh({ refresh_token: refreshToken });
      return {
        data: response.data,
        error: null,
        correlationId: response.correlationId,
      };
    } catch (error) {
      if (error instanceof ApiError) {
        return {
          data: null,
          error: {
            detail: error.getUserMessage(),
            status: error.problem.status,
          },
          correlationId: error.correlationId,
        };
      }

      return {
        data: null,
        error: {
          detail: 'Token refresh failed',
          status: 500,
        },
        correlationId: undefined,
      };
    }
  },

  async verify() {
    try {
      const response = await authService.verify();
      return {
        data: response.data,
        error: null,
        correlationId: response.correlationId,
      };
    } catch (error) {
      if (error instanceof ApiError) {
        return {
          data: null,
          error: {
            detail: 'Token verification failed',
            status: 401,
          },
          correlationId: error.correlationId,
        };
      }

      return {
        data: null,
        error: {
          detail: 'Token verification failed',
          status: 401,
        },
        correlationId: undefined,
      };
    }
  },

  logout() {
    authService.logout();
  },
};

// Also export the new service for direct use
export { authService };
