/**
 * Authentication Service Client
 * Type-safe client for auth endpoints (B0.2)
 * Port 4010
 */

import { authClient, type ApiResponse } from '@/lib/api-client-base';
import type { paths } from '@/types/api/auth';

type LoginRequest = paths['/api/auth/login']['post']['requestBody']['content']['application/json'];
type LoginResponse = paths['/api/auth/login']['post']['responses']['200']['content']['application/json'];
type RefreshRequest = paths['/api/auth/refresh']['post']['requestBody']['content']['application/json'];
type RefreshResponse = paths['/api/auth/refresh']['post']['responses']['200']['content']['application/json'];
type VerifyResponse = paths['/api/auth/verify']['get']['responses']['200']['content']['application/json'];

export class AuthService {
  /**
   * Login with email and password
   * POST /api/auth/login
   */
  async login(credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    console.log('[AuthService] Attempting login, authClient baseURL:', (authClient as any).baseURL);
    try {
      const result = await authClient.post<LoginResponse>('/api/auth/login', credentials);
      console.log('[AuthService] Login successful');
      return result;
    } catch (error) {
      console.error('[AuthService] Login failed:', error);
      throw error;
    }
  }

  /**
   * Refresh access token
   * POST /api/auth/refresh
   */
  async refresh(data: RefreshRequest): Promise<ApiResponse<RefreshResponse>> {
    return authClient.post<RefreshResponse>('/api/auth/refresh', data);
  }

  /**
   * Verify current token
   * GET /api/auth/verify (token passed via Authorization header)
   */
  async verify(): Promise<ApiResponse<VerifyResponse>> {
    return authClient.get<VerifyResponse>('/api/auth/verify');
  }

  /**
   * Logout (clear client-side tokens)
   */
  logout(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }
}

export const authService = new AuthService();
