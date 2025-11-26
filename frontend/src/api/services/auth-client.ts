/**
 * Authentication Service Client
 * Type-safe client for auth endpoints
 */

import { authClient, type ApiResponse } from '@/lib/api-client-base';
import type { paths } from '@/types/api/auth';

type LoginRequest = paths['/api/auth/login']['post']['requestBody']['content']['application/json'];
type LoginResponse = paths['/api/auth/login']['post']['responses']['200']['content']['application/json'];
type RefreshRequest = paths['/api/auth/refresh']['post']['requestBody']['content']['application/json'];
type RefreshResponse = paths['/api/auth/refresh']['post']['responses']['200']['content']['application/json'];
type VerifyResponse = paths['/api/auth/verify']['post']['responses']['200']['content']['application/json'];

export class AuthService {
  /**
   * Login with email and password
   */
  async login(credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    return authClient.post<LoginResponse>('/api/auth/login', credentials);
  }

  /**
   * Refresh access token
   */
  async refresh(data: RefreshRequest): Promise<ApiResponse<RefreshResponse>> {
    return authClient.post<RefreshResponse>('/api/auth/refresh', data);
  }

  /**
   * Verify current token
   */
  async verify(token: string): Promise<ApiResponse<VerifyResponse>> {
    return authClient.post<VerifyResponse>('/api/auth/verify', { token });
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
