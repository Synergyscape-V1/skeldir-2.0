import StripeLogo from './logos/StripeLogo';
import GoogleLogo from './logos/GoogleLogo';
import ShopifyLogo from './logos/ShopifyLogo';
import SquareLogo from './logos/SquareLogo';

interface PlatformBadgeProps {
  platform: string;
  brandColor: string;
}

export default function PlatformBadge({ platform, brandColor }: PlatformBadgeProps) {
  // Map platform names to logo components
  const logoComponents: Record<string, React.ReactNode> = {
    'Stripe': <StripeLogo />,
    'Google': <GoogleLogo />,
    'Shopify': <ShopifyLogo />,
    'Square': <SquareLogo />,
  };

  const logo = logoComponents[platform];

  if (!logo) {
    return null;
  }

  return (
    <div
      className="absolute top-3 left-3 z-10 flex items-center justify-center rounded-full"
      style={{
        width: '28px',
        height: '28px',
        backgroundColor: brandColor,
        border: '2px solid white',
        boxShadow: '0 2px 4px rgba(0, 0, 0, 0.15)',
      }}
      data-testid={`badge-${platform.toLowerCase()}`}
    >
      <div className="flex items-center justify-center" style={{ transform: 'scale(0.35)' }}>
        {logo}
      </div>
    </div>
  );
}
