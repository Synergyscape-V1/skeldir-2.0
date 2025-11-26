import { useMemo } from 'react';
import { useApiClient, type ApiClientConfig, type ApiResponse } from './use-api-client';
import { useErrorBanner } from './use-error-banner';
import { ErrorBannerMapper } from '@/lib/error-banner-mapper';

export interface ApiClientWithBannersConfig extends ApiClientConfig {
  suppressBanners?: boolean;
  customBannerMapper?: (error: any) => ReturnType<typeof ErrorBannerMapper.mapApiError> | null;
}

export function useApiClientWithBanners(config?: ApiClientWithBannersConfig) {
  const { suppressBanners = false, customBannerMapper, ...apiConfig } = config || {};
  const apiClient = useApiClient(apiConfig);
  const { showBanner } = useErrorBanner();

  const wrapWithBanners = <TReq, TRes>(
    requestFn: (url: string, ...args: any[]) => Promise<ApiResponse<TRes>>
  ) => {
    return async (url: string, ...args: any[]): Promise<ApiResponse<TRes>> => {
      const response = await requestFn(url, ...args);

      if (response.error && !suppressBanners) {
        const bannerConfig = customBannerMapper
          ? customBannerMapper(response.error)
          : ErrorBannerMapper.mapApiError({
              status: response.error.status,
              code: response.error.code,
              message: response.error.message,
              correlationId: response.error.correlationId,
              endpoint: url,
            });

        if (bannerConfig) {
          showBanner(bannerConfig);
        }
      }

      return response;
    };
  };

  return useMemo(() => ({
    request: apiClient.request,
    get: wrapWithBanners(apiClient.get),
    post: wrapWithBanners(apiClient.post),
    put: wrapWithBanners(apiClient.put),
    patch: wrapWithBanners(apiClient.patch),
    delete: wrapWithBanners(apiClient.delete),
  }), [apiClient, suppressBanners, customBannerMapper, showBanner]);
}
