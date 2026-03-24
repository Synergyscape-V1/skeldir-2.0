# Platform Icon Asset Manifest

## Purpose
Brand-accurate, production-safe channel logos for the Channel Performance table in all five agent iterations.

## Sources and Licensing
- `google-ads.svg`
  - Source URL: `https://upload.wikimedia.org/wikipedia/commons/c/c7/Google_Ads_logo.svg`
  - Adaptation: icon-only extraction (no typography), original brand colors preserved
  - License: As listed on Wikimedia Commons page for the asset
- `meta-ads.svg`
  - Source URL: `https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/meta.svg`
  - Adaptation: colorized to Meta brand blue for icon-only usage
  - License: CC0 1.0 (Simple Icons)
- `tiktok-ads.svg`
  - Source URL: `https://upload.wikimedia.org/wikipedia/en/a/a9/TikTok_logo.svg`
  - Adaptation: icon-only extraction (no typography), multicolor note preserved
  - License: As listed on Wikimedia Commons page for the asset
- `pinterest-ads.svg`
  - Source URL: `https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/pinterest.svg`
  - Adaptation: colorized to Pinterest brand red for icon-only usage
  - License: CC0 1.0 (Simple Icons)
- `linkedin-ads.svg`
  - Source URL: `https://upload.wikimedia.org/wikipedia/commons/8/81/LinkedIn_icon.svg`
  - License: As listed on Wikimedia Commons page for the asset

- `klaviyo.svg`
  - Source: User-provided brand export (`Klaviyo_idKtt8wKCb_0.svg` from `download-idOL_ClNhe-1774208345691.zip`)
  - Adaptation: Renamed to `klaviyo.svg` for stable URL; icon mark only (compact viewBox)
  - License: Use per Klaviyo brand guidelines

## Integration Notes
- Mapped by normalized channel name in `src/comparison/AgentShellCommandCenter.tsx`.
- Uses 16x16 logos with descriptive alt text.
- Includes alias mapping for `facebook -> meta` and `linkden -> linkedin`.
