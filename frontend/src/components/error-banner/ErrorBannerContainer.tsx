import { useContext } from 'react';
import { ErrorBannerContextInstance } from './ErrorBannerContext';
import { ErrorBanner } from './ErrorBanner';

export function ErrorBannerContainer() {
  const context = useContext(ErrorBannerContextInstance);

  if (!context) {
    return null;
  }

  const { banners, dismissBanner } = context;

  return (
    <>
      {banners.map((banner, index) => (
        <ErrorBanner
          key={banner.id}
          config={banner}
          index={index}
          totalBanners={banners.length}
          onDismiss={dismissBanner}
        />
      ))}
    </>
  );
}
