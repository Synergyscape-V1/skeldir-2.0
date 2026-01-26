# SKELDIR Marketing Website

**Public-facing marketing site for skeldir.com**

> Part of the skeldir-2.0 unified monorepo. This directory contains the marketing website that showcases SKELDIR's attribution intelligence platform to prospective customers.

---

## Overview

This marketing site is built with production-grade technologies optimized for:
- **Performance**: Fast page loads, SEO optimization, Core Web Vitals
- **Developer Experience**: Hot reload, TypeScript, modern tooling
- **Deployment**: Edge-optimized static generation with Vercel/Netlify
- **Brand Consistency**: Shared design tokens with main product (`../frontend/`)

---

## Tech Stack

### Recommended: Next.js 14+ (App Router)
- **Why**: Industry-standard for marketing sites, excellent SEO, Image optimization
- **Benefits**: React Server Components, built-in analytics, Vercel deployment

### Alternative: Astro 4+
- **Why**: Ultra-fast static sites, partial hydration, framework-agnostic
- **Benefits**: Better Lighthouse scores, smaller bundle sizes

**Current Setup**: [Choose based on team preference]

---

## Directory Structure

```
marketing/
├── README.md                    # This file
├── package.json                 # Dependencies and scripts
├── tsconfig.json                # TypeScript configuration
├── next.config.js               # Next.js configuration (or astro.config.mjs)
├── tailwind.config.ts           # Tailwind CSS configuration
├── .env.local.example           # Environment variables template
├── public/                      # Static assets
│   ├── favicon.ico
│   ├── images/                  # Product screenshots, hero images
│   ├── videos/                  # Demo videos, testimonials
│   └── fonts/                   # Custom brand fonts
├── src/
│   ├── app/                     # Next.js App Router (or pages/)
│   │   ├── layout.tsx           # Root layout
│   │   ├── page.tsx             # Homepage
│   │   ├── pricing/
│   │   ├── features/
│   │   ├── customers/
│   │   ├── blog/
│   │   └── contact/
│   ├── components/              # Reusable UI components
│   │   ├── ui/                  # Base components (Button, Card, etc.)
│   │   ├── sections/            # Page sections (Hero, Features, CTA)
│   │   ├── layout/              # Layout components (Header, Footer)
│   │   └── forms/               # Contact, demo request forms
│   ├── lib/                     # Utilities
│   │   ├── analytics.ts         # GA4, Mixpanel integration
│   │   ├── api.ts               # API client for backend
│   │   └── seo.ts               # SEO utilities
│   ├── styles/                  # Global styles
│   │   └── globals.css          # Tailwind imports, global CSS
│   └── content/                 # Content (MDX blog posts, case studies)
├── tests/                       # E2E tests (Playwright)
└── .github/                     # CI/CD workflows (optional)
```

---

## Key Pages

### 1. Homepage (`/`)
- Hero section with value proposition
- Social proof (logos, testimonials)
- Feature highlights
- CTA (Book Demo, Start Free Trial)

### 2. Features (`/features`)
- Attribution Intelligence
- Budget Optimization
- Investigation Queue
- Multi-channel tracking

### 3. Pricing (`/pricing`)
- Tier comparison (Starter, Professional, Enterprise)
- Feature matrix
- FAQ

### 4. Customers (`/customers` or `/case-studies`)
- Customer testimonials
- Case studies
- ROI statistics

### 5. Blog (`/blog`)
- Thought leadership
- Product updates
- SEO content

### 6. Contact (`/contact`)
- Contact form
- Demo request
- Support links

---

## Integration with Monorepo

### Shared Assets
```typescript
// Reference frontend design tokens
import { colors, typography } from '../frontend/src/styles/tokens';

// Use shared logo assets
import logo from '../frontend/public/assets/platform-logos/skeldir-logo.svg';
```

### API Integration
```typescript
// Contact form submission to backend
import { apiClient } from './lib/api';

await apiClient.post('/api/v1/marketing/contact', formData);
```

### Environment Variables
```bash
# Backend API
NEXT_PUBLIC_API_URL=https://api.skeldir.com

# Analytics
NEXT_PUBLIC_GA_ID=G-XXXXXXXXXX
NEXT_PUBLIC_MIXPANEL_TOKEN=xxxxx

# Forms
NEXT_PUBLIC_HUBSPOT_PORTAL_ID=xxxxx
```

---

## Quick Start

### Installation
```bash
cd marketing/
npm install
```

### Development
```bash
npm run dev
# Opens at http://localhost:3000
```

### Build
```bash
npm run build
npm run start  # Production server
```

### Testing
```bash
npm run test        # Unit tests
npm run test:e2e    # Playwright E2E tests
npm run lint        # ESLint
```

---

## Deployment

### Vercel (Recommended)
1. Connect GitHub repository
2. Set root directory to `marketing/`
3. Configure environment variables
4. Deploy

**Custom Domain**: `www.skeldir.com` or `skeldir.com`

### Alternative: Netlify, Cloudflare Pages
Same process, configure build settings:
```toml
[build]
  base = "marketing/"
  command = "npm run build"
  publish = ".next" # or "dist/" for Astro
```

---

## CI/CD Integration

### GitHub Actions Workflow
```yaml
name: Marketing Site CI/CD

on:
  push:
    paths:
      - 'marketing/**'
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: cd marketing && npm ci
      - run: cd marketing && npm run build
      - run: cd marketing && npm run test:e2e
      # Deploy to Vercel/Netlify
```

---

## Design System Alignment

### Brand Colors (Sync with Frontend)
```typescript
// tailwind.config.ts
const colors = {
  brand: {
    primary: '#your-brand-color',
    secondary: '#your-secondary-color',
  },
  // ... match frontend/src/styles/tokens.ts
};
```

### Typography
- Use same font family as product app
- Maintain visual consistency for brand recognition

### Components
- Share Button, Card, Badge components where applicable
- Marketing-specific: Hero, Testimonial, PricingCard

---

## SEO Best Practices

### Meta Tags
```tsx
// app/layout.tsx or pages/_app.tsx
export const metadata = {
  title: 'SKELDIR - Attribution Intelligence Platform',
  description: 'Optimize marketing budgets with AI-powered attribution...',
  openGraph: {
    title: 'SKELDIR',
    description: '...',
    images: ['/og-image.png'],
  },
};
```

### Sitemap & Robots.txt
- Auto-generated by Next.js/Astro
- Submit to Google Search Console

### Performance
- Target Lighthouse score: 95+
- Core Web Vitals: LCP < 2.5s, FID < 100ms, CLS < 0.1

---

## Analytics & Tracking

### Google Analytics 4
```typescript
// lib/analytics.ts
export const trackEvent = (eventName: string, params: any) => {
  if (typeof window !== 'undefined' && window.gtag) {
    window.gtag('event', eventName, params);
  }
};
```

### Conversion Tracking
- Demo requests
- Sign-up clicks
- Pricing page views
- Blog engagement

---

## Content Strategy

### Messaging
- **Value Prop**: "Stop guessing where your marketing budget goes"
- **Target Audience**: CFOs, Marketing Ops, Budget Owners
- **Differentiation**: Attribution + Budget Optimization in one platform

### Social Proof
- Customer logos
- Testimonials with ROI stats
- Case studies with metrics

---

## Development Workflow

1. **Design** → Figma mockups reviewed by product team
2. **Build** → Implement in Next.js/Astro with Tailwind
3. **Review** → Preview deployment on Vercel
4. **Test** → E2E tests, Lighthouse audit
5. **Deploy** → Merge to main → Auto-deploy to production

---

## Maintenance

### Regular Updates
- Product screenshots (when UI changes)
- Pricing (when tiers change)
- Blog posts (weekly/bi-weekly)
- Testimonials (quarterly)

### Monitoring
- Uptime (Vercel Analytics)
- Error tracking (Sentry)
- Performance (Lighthouse CI)

---

## Contributing

See root monorepo `CONTRIBUTING.md` for guidelines.

### Marketing-Specific Guidelines
- Keep content aligned with product roadmap
- Coordinate feature announcements with product launches
- Maintain brand voice consistency

---

## Support

For questions about the marketing site:
- **Technical**: Check `../docs/` for monorepo architecture
- **Content**: Coordinate with product/marketing team
- **Design**: Reference Figma design system

---

## Next Steps

1. **Choose Framework**: Next.js or Astro
2. **Initialize Project**: Run `npx create-next-app@latest` or `npm create astro@latest`
3. **Copy Your Files**: Move existing landing page code here
4. **Configure Deployment**: Set up Vercel/Netlify
5. **Launch**: Deploy to production

---

**Last Updated**: January 2026  
**Maintainer**: SKELDIR Development Team
