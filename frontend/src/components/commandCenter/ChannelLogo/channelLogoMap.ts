import channelsPlaceholder from '../../../assets/icons/nav/channels.svg';
import homeLogo from '../../../assets/icons/nav/home.svg';
import paypalLogo from '../../../assets/icons/nav/PayPal_Logo_Icon_2014.svg';
import shopifyLogo from '../../../assets/icons/nav/shopify.svg';
import tiktokLogo from '../../../assets/icons/nav/tiktok.svg';
import woocommerceLogo from '../../../assets/icons/nav/WooCommerce_logo_(2015).svg';
import emailLogo from '../../../assets/icons/channels/email.svg';
import googleAdsLogo from '../../../assets/icons/channels/google-ads.svg';
import linkedinLogo from '../../../assets/icons/channels/linkedin.svg';
import metaLogo from '../../../assets/icons/channels/meta.svg';
import paidSocialLogo from '../../../assets/icons/channels/paid-social.svg';
import searchLogo from '../../../assets/icons/channels/search.svg';
import stripeLogo from '../../../assets/icons/channels/stripe.svg';

/**
 * Approved placeholder for channels without a dedicated platform SVG in the asset library.
 */
export const CHANNEL_LOGO_PLACEHOLDER = channelsPlaceholder;

/** Claim-source and commerce-provider keys map to vendor/platform marks. */
const CLAIM_SOURCE_LOGO: Record<string, string> = {
  stripe: stripeLogo,
  shopify: shopifyLogo,
  woocommerce: woocommerceLogo,
  paypal: paypalLogo,
  google_ads: googleAdsLogo,
  meta_ads: metaLogo,
  tiktok_ads: tiktokLogo,
  linkedin_ads: linkedinLogo,
  email: emailLogo,
  organic_search: searchLogo,
};

/**
 * Attribution / campaign-class keys are not vendors.
 * Never bind these to Meta, Google, LinkedIn, etc. — one class can span many platforms.
 */
const ATTRIBUTION_CHANNEL_LOGO: Record<string, string> = {
  paid_search: searchLogo,
  paid_social: paidSocialLogo,
  email: emailLogo,
  direct: homeLogo,
  organic: searchLogo,
  referral: channelsPlaceholder,
  creator: channelsPlaceholder,
  branded: channelsPlaceholder,
  affiliate: channelsPlaceholder,
};

export function resolveChannelLogoSrc(claimSource: string): string {
  return CLAIM_SOURCE_LOGO[claimSource] ?? CHANNEL_LOGO_PLACEHOLDER;
}

export function isChannelLogoPlaceholder(claimSource: string): boolean {
  return resolveChannelLogoSrc(claimSource) === CHANNEL_LOGO_PLACEHOLDER;
}

export function resolveAttributionChannelIconSrc(channel: string): string {
  return ATTRIBUTION_CHANNEL_LOGO[channel] ?? CHANNEL_LOGO_PLACEHOLDER;
}
