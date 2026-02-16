# Channel Platform Logo Attribution

## SVG Logo Sources

All platform logos are hand-traced monochrome SVG paths based on publicly available brand marks.
They render via `currentColor` for theme safety (light/dark mode compatible).

| Platform | Source Reference | License Notes |
|----------|-----------------|---------------|
| Meta (Facebook) | Facebook Brand Resources | Simplified monochrome trace, non-official |
| Google | Google Brand Guidelines | Simplified 4-path monochrome, non-official |
| TikTok | TikTok Brand Resources | Simplified monochrome trace, non-official |
| LinkedIn | LinkedIn Brand Resources | Simplified monochrome trace, non-official |
| Pinterest | Pinterest Brand Resources | Simplified monochrome trace, non-official |
| Snapchat | Snapchat Brand Resources | Simplified monochrome trace, non-official |
| X (Twitter) | X Brand Resources | Simplified monochrome trace, non-official |
| Fallback | Lucide Icons (`Link2`) | ISC License |

## Modifications

- All logos simplified to single-color `currentColor` fill (no brand colors hardcoded)
- Rendered as typed React SVG components (`.tsx`) for tree-shakeability
- Sizes configurable via `size` prop, default 20px
- All use `aria-hidden="true"` — the channel name provides the accessible label

## Usage

```tsx
import { getChannelLogo } from '@/assets/logos/channels';
const Logo = getChannelLogo('meta'); // MetaLogo component
const Fallback = getChannelLogo('unknown'); // FallbackLogo component
```
