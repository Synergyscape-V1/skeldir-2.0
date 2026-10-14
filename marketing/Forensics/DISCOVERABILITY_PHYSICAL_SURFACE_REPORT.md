# Skeldir Physical Surface Governance Report

**Phase:** D0 — Evidence Freeze  
**Date:** 2026-05-21  
**Status:** Baseline classification complete; no physical split performed

---

## 1. Root Layout Analysis

### Single Root Layout

All Next.js routes share **one root layout** at `src/app/layout.tsx`. This layout:

- Is a **Server Component** (no `"use client"` directive)
- Loads three Google Fonts: DM Sans (body), Playfair Display (accent), IBM Plex Sans Condensed (hero)
- Sets global metadata via Next.js Metadata API (`metadataBase`, title, description, OG, Twitter, icons, manifest)
- Renders `<NavigationWrapper />` on every page (marketing, transactional, auth)
- Renders `{children}` directly in `<body>` — no additional providers or context wrappers

**There are no route groups** providing separate root layouts. Marketing pages (`/`, `/product`, `/pricing`, `/agencies`, `/resources`) and auth pages (`/Login`, `/signup`) and transactional pages (`/book-demo`, `/book-demo/thank-you`) all render within the same root layout.

### Nested Layouts

| Layout | Path | Type | Purpose |
|---|---|---|---|
| Root | `src/app/layout.tsx` | Server Component | Global metadata, fonts, navigation |
| Resources | `src/app/resources/layout.tsx` | Server Component | Resources section metadata + canonical |
| Article | `src/app/resources/[slug]/layout.tsx` | Server Component | Per-article metadata, `generateStaticParams` |

**No other nested layouts exist.** Login, signup, book-demo, pricing, product, agencies pages have no layout files.

---

## 2. Client Component Analysis

### `"use client"` Pages (in `src/app/`)

| Page | Path | Reason for Client Directive |
|---|---|---|
| `/book-demo` | `src/app/book-demo/page.tsx` | Cal.com embed, form state, `useSearchParams`, `useRouter` |
| `/book-demo/thank-you` | `src/app/book-demo/thank-you/page.tsx` | `useRouter` for redirect, `useEffect` for timer |
| `/product` | `src/app/product/page.tsx` | `useRouter` for navigation |
| `/resources` | `src/app/resources/page.tsx` | Client-side filtering/state |
| `/resources/[slug]` | `src/app/resources/[slug]/page.tsx` | `useState`/`useEffect` for slug resolution (the cause of the Loading... defect) |

### Server Component Pages (in `src/app/`)

| Page | Path |
|---|---|
| `/` (homepage) | `src/app/page.tsx` |
| `/Login` | `src/app/Login/page.tsx` |
| `/signup` | `src/app/signup/page.tsx` |
| `/agencies` | `src/app/agencies/page.tsx` |
| `/pricing` | `src/app/pricing/page.tsx` |

### `"use client"` Components (in `src/components/`)

42 client components exist across:
- `components/article/` — All 10 article components are client components
- `components/layout/` — 20 layout components are client components (including Footer, Navigation, HeroSection, etc.)
- `components/pricing/` — 7 pricing components are client components
- `components/resources/` — 4 resource components are client components
- `components/ui/` — 1 UI component (`label.tsx`)

---

## 3. Shared Client Providers

**None.** The root layout does not wrap children in any context providers. There is:
- No `SessionProvider` or auth context
- No `ThemeProvider`
- No global state management (no Redux, Zustand, Jotai, etc.)
- No analytics provider

The only shared component rendered from the root layout is `<NavigationWrapper />`, which is a client component providing the navigation bar.

---

## 4. Auth and API Client Imports

### Login Page (`/Login`)
- Server Component page that imports `<LoginPage />` from `@/components/auth/login/LoginPage`
- `LoginPage` is a **client component** providing a login form UI
- **No actual auth API client** — the form is UI-only (no `fetch`, no auth SDK, no session management)

### Signup Page (`/signup`)
- Server Component page that imports `<SignUpPage />` from `@/components/auth/signup/SignUpPage`
- `SignUpPage` is a **client component** providing a signup form UI
- **No actual auth API client** — the form is UI-only

### Book-Demo Page (`/book-demo`)
- Client Component page
- Imports Cal.com embed script via `next/script`
- Makes a `fetch()` POST to `/book-demo` for Netlify Forms submission
- **No auth imports**, but integrates external Cal.com booking service

**Conclusion:** No marketing page imports auth or API client logic. Login and signup are shell forms without backend integration in this codebase.

---

## 5. Physical Co-location Assessment

### Which routes share the same root layout?

All 10 page routes share the single root layout:
- Marketing: `/`, `/product`, `/pricing`, `/agencies`, `/resources`, `/resources/[slug]`
- Transactional: `/book-demo`, `/book-demo/thank-you`
- Auth: `/Login`, `/signup`

### Which routes are `"use client"` pages?

5 of 10: `/book-demo`, `/book-demo/thank-you`, `/product`, `/resources`, `/resources/[slug]`

### Which routes import shared client providers?

None — no shared providers exist.

### Which routes import auth or API client logic?

None at the page level. `/Login` and `/signup` import auth UI components, but those components contain no API client logic in the current codebase.

### Which transactional/auth routes are physically co-located with marketing?

All of them. `/Login`, `/signup`, `/book-demo`, `/book-demo/thank-you` are in the same `src/app/` tree as marketing routes, share the same root layout, and export to the same `out/` directory.

### Does any public marketing route import authenticated-app-only code?

No. No marketing page imports from `@/components/auth/` or any auth-specific module.

### Are chunks shared between marketing and auth/transactional routes?

**Inconclusive.** Without detailed webpack/turbopack chunk analysis, we cannot definitively determine chunk sharing. However:
- The root layout JS (fonts, NavigationWrapper) is shared across all pages
- `_next/static/chunks/` contains 27 JS files; which routes consume which chunks requires build manifest analysis
- The Footer component is imported independently per page (not in root layout), so it likely gets bundled per entry point

---

## 6. Physical Split Assessment

### Physical split required during D0

**Not established.** D0 does not claim safety or non-requirement when evidence is inconclusive.

### Current condition

- All Next.js routes share a **single root layout** (`src/app/layout.tsx`)
- All routes export into one static `out/` directory via `output: 'export'`
- All routes share `_next/static/chunks/` from a single build graph
- Detailed per-route chunk coupling is **inconclusive** without build manifest analysis

### Risk level

**Structural isolation risk — not yet proven breach.**

Import boundary scan (2026-05-21):

| Route class | Isolation status | Evidence |
|---|---|---|
| `marketing_static` | `inconclusive` | No auth/backend/token/dashboard-provider imports detected in page sources |
| `auth_static` (`/Login`, `/signup`) | `risk` | Pages import `@/components/auth/*` UI; co-located with marketing in same static export |
| `transactional_static` (`/book-demo`) | `inconclusive` | Client shell with spinner body; no backend API imports |
| `transactional_static` (`/book-demo/thank-you`) | `inconclusive` | Redirect-only page |
| `review_public_static` | `safe` | Standalone HTML, no Next.js chunk sharing |

No secrets, private API base URLs, token handlers, or tenant-aware runtime code detected in marketing page sources. Login form contains a `/dashboard` redirect string (UI placeholder, not authenticated app code).

### D1 allowed scope

**Marketing-static retrieval fixes only** — article SSR, hub HTML, commercial page body integrity. No auth/app split required for D1.

### Deferred split trigger

Before authenticated dashboard, Trust API runtime, or tenant-aware app surfaces ship: **route-group/app-level split or equivalent isolation proof required.**

### Route registry isolation fields (v2)

Each route now records:

```text
imports_auth_code
imports_backend_api_client
imports_tenant_logic
imports_token_handling
imports_dashboard_provider
shared_root_layout
shared_client_chunks_observed
isolation_status: safe | risk | breach | inconclusive
```

Harness rule: FAIL if `marketing_static` routes import backend/token/dashboard-provider modules.

---

## 7. Login / Signup / Book-Demo Classification

| Route | Physical Surface | Root Layout | Noindex Required | Sitemap Excluded | Notes |
|---|---|---|---|---|---|
| `/Login` | `auth_static` | Shared with marketing | **Yes** | **Yes** | Capital-L URL is a casing issue; should be `/login` |
| `/signup` | `auth_static` | Shared with marketing | **Yes** | **Yes** | UI shell only, no auth backend |
| `/book-demo` | `transactional_static` | Shared with marketing | **Planned after D1/D2** | **No** (`sitemap_required=false`) | `indexable_candidate`, `active_defective_until_static_body_verified` — spinner shell, missing canonical, broken /privacy link |
| `/book-demo/thank-you` | `transactional_static` | Shared with marketing | **Yes** (`noindex_required=true`, `noindex_implemented=false`) | **Yes** | Auto-redirect to `/` after 5s |

---

## 8. Implementation Review Artifacts

| Route | Physical Surface | Source | Type | Treatment |
|---|---|---|---|---|
| `/implementations/agent-a/` | `review_public_static` | `public/implementations/agent-a/index.html` | Standalone HTML (Storybook comparison) | Should be `noindex`, excluded from sitemap |
| `/implementations/agent-b/` | `review_public_static` | `public/implementations/agent-b/index.html` | Standalone HTML | Should be `noindex`, excluded from sitemap |
| `/implementations/agent-c/` | `review_public_static` | `public/implementations/agent-c/index.html` | Standalone HTML | Should be `noindex`, excluded from sitemap |
| `/implementations/agent-d/` | `review_public_static` | `public/implementations/agent-d/index.html` | Standalone HTML | Should be `noindex`, excluded from sitemap |
| `/implementations/agent-e/` | `review_public_static` | `public/implementations/agent-e/index.html` | Standalone HTML | Should be `noindex`, excluded from sitemap |

These are design comparison artifacts from a Storybook orchestration run (`run-2026-02-19-orch-sol-art-003`). They should NOT be indexed or appear in sitemap. Current state: no `noindex` tag, no `robots.txt` blocking, fully accessible to crawlers.

---

*Generated: 2026-05-21 | Phase: D0 | Status: Baseline physical surface classification complete*
