# Skeldir Discoverability Evidence Freeze

**Phase:** D0 — Evidence Freeze  
**Date:** 2026-05-21  
**Audit source:** `C:\Users\ayewhy\Skeldir Webpage\Skeldir_Webpage_Discoverability_Audit_Report.md`  
**Status:** Frozen baseline (v2 corrective applied 2026-05-21)  
**Repo scope addendum:** `D0_REPO_SCOPE_RESOLUTION.md`

---

## 1. Git Branch and Deployment Authority

### Current Branch

```
$ git branch --show-current
master
```

### Primary Branch

`master` — this is the current working branch on the local repo.

### Remote HEAD

```
$ git remote -v
origin  https://github.com/Muk223/skeldir-2.0.git (fetch)
origin  https://github.com/Muk223/skeldir-2.0.git (push)
```

**Note:** The local `marketing/` directory's git root is `C:/Users/ayewhy` (the user's home directory), with no commits yet on the `master` branch. This is a misconfigured git topology — the git repo encompasses the entire user home directory, not just the project.

### Production-Deployed Clone

A separate, properly-scoped git repo exists at:

```
C:\Users\ayewhy\Skeldir Webpage\skeldir-production-main-deploy-20260518

$ git -C skeldir-production-main-deploy-20260518 branch -vv
* codex/marketing-production-missing-lib 43921ca6 [origin/codex/marketing-production-missing-lib] Add ignored marketing metadata sources
  main                                   c1f25f43 [origin/main: ahead 1, behind 2] Deploy complete marketing webpage update

$ git -C skeldir-production-main-deploy-20260518 remote -v
origin  https://github.com/Synergyscape-V1/skeldir-2.0.git (fetch)
origin  https://github.com/Synergyscape-V1/skeldir-2.0.git (push)
```

**Observation:** Two GitHub organizations host copies of this repo:
- `Muk223/skeldir-2.0` (personal fork, referenced by local `marketing/`)
- `Synergyscape-V1/skeldir-2.0` (organization repo, referenced by production clone)

### Push Target

D0 artifacts will be committed to the local `marketing/` directory under the `master` branch targeting `origin` (`Muk223/skeldir-2.0.git`). The production Netlify deployment reads from `Synergyscape-V1/skeldir-2.0.git`.

---

## 2. Active Source Directory

**Active source:** `marketing/` (within `C:\Users\ayewhy\Skeldir Webpage\marketing\`)  
**Evidence:** Most recent file edits are 2026-05-20. All current development work occurs here.

---

## 3. Framework and Version

```json
// marketing/package.json
{
  "dependencies": {
    "next": "16.1.1",
    "react": "19.2.3",
    "react-dom": "19.2.3"
  }
}
```

**Framework:** Next.js 16.1.1 (App Router)  
**React:** 19.2.3  
**CSS:** Tailwind CSS v4  
**Build tool:** Turbopack (via `turbopack: { root: __dirname }` in next.config.ts)

---

## 4. Export Mode

```typescript
// marketing/next.config.ts
const nextConfig: NextConfig = {
  output: 'export',
  images: { unoptimized: true },
  turbopack: { root: __dirname },
};
```

**Mode:** Static export (SSG). All pages rendered to flat HTML at build time.  
**Implication:** No server-side rendering at request time. `"use client"` pages render their initial state (loading shells) permanently into static HTML.

---

## 5. Deployment Target

```toml
# skeldir-production-main-deploy-20260518/netlify.toml
[build]
  base = "marketing"
  command = "npm run build"
  publish = "out"
  ignore = "if [ -z \"$CACHED_COMMIT_REF\" ] || [ -z \"$COMMIT_REF\" ]; then exit 1; fi; git diff --quiet \"$CACHED_COMMIT_REF\" \"$COMMIT_REF\" -- marketing/"
```

**Target:** Netlify  
**Base:** `marketing/`  
**Build command:** `npm run build` (→ `next build`)  
**Publish directory:** `out/`  
**Ignore rule:** Only rebuilds when `marketing/` changes  
**No:** `_headers`, `_redirects`, edge functions, middleware

---

## 6. Public/Static Directory

**Path:** `marketing/public/`

Contents:
- `images/` — Brand logos, partner logos, ad platform logos, AI tool logos, article hero images, product screenshots (73+ files)
- `assets/images/` — Responsive image sets (hero, solution-articulation, agencies)
- `agencies/` — Agency-specific images (9 PNGs)
- `implementations/` — Storybook comparison artifacts (agent-a through agent-e, reference, README, manifest)
- `videos/` — `demo-video.mp4` (86 MB)

**Missing from public/:**
- ❌ `robots.txt`
- ❌ `sitemap.xml`
- ❌ `llms.txt`
- ❌ `llms-full.txt`
- ❌ `_headers`
- ❌ `_redirects`

---

## 7. Route Inventory — Source (`src/app/`)

| # | Source Path | Resolved URL | Server/Client | Metadata |
|---|---|---|---|---|
| 1 | `src/app/page.tsx` | `/` | Server | Root layout metadata only |
| 2 | `src/app/product/page.tsx` | `/product` | Client | Root layout metadata only |
| 3 | `src/app/pricing/page.tsx` | `/pricing` | Server | Root layout metadata only |
| 4 | `src/app/agencies/page.tsx` | `/agencies` | Server | Per-page metadata |
| 5 | `src/app/resources/page.tsx` | `/resources` | Client | Resources layout metadata + canonical |
| 6 | `src/app/resources/[slug]/page.tsx` | `/resources/:slug` | Client | Per-article metadata + canonical + generateStaticParams |
| 7 | `src/app/book-demo/page.tsx` | `/book-demo` | Client | Root layout metadata only |
| 8 | `src/app/book-demo/thank-you/page.tsx` | `/book-demo/thank-you` | Client | Root layout metadata only |
| 9 | `src/app/Login/page.tsx` | `/Login` | Server | Per-page metadata |
| 10 | `src/app/signup/page.tsx` | `/signup` | Server | Per-page metadata |

### App Router Semantics

- **Route groups:** None
- **Parallel routes:** None
- **Intercepting routes:** None
- **Dynamic segments:** One (`[slug]` under `resources/`)
- **Catch-all segments:** None
- **Metadata routes (sitemap.ts, robots.ts):** None (both missing)
- **Route handlers (route.ts):** None
- **Layouts:** 3 (root, resources, resources/[slug])

---

## 8. Route Inventory — App Router Normalized

Since no route groups, parallel slots, or intercepting routes exist, filesystem paths map directly to URLs with one normalization:

- `[slug]` → expanded by `generateStaticParams()` to 4 concrete slugs

| Source Pattern | Concrete URLs |
|---|---|
| `resources/[slug]` | `/resources/why-your-attribution-numbers-never-match` |
| | `/resources/roas-is-not-a-number-its-a-range` |
| | `/resources/attribution-methods-answer-different-questions` |
| | `/resources/confidently-defend-budget-shift` |

---

## 9. Route Inventory — Build Output (`marketing/out/`)

| # | Output Path | Served URL | Size | Notes |
|---|---|---|---:|---|
| 1 | `out/index.html` | `/` | 166 KB | No canonical, no JSON-LD |
| 2 | `out/product.html` | `/product` | 167 KB | No canonical, no JSON-LD |
| 3 | `out/pricing.html` | `/pricing` | 63 KB | No canonical, no JSON-LD |
| 4 | `out/agencies.html` | `/agencies` | 100 KB | No canonical, no JSON-LD |
| 5 | `out/resources.html` | `/resources` | 57 KB | Has canonical |
| 6 | `out/resources/why-your-attribution-numbers-never-match.html` | `/resources/why-your-attribution-numbers-never-match` | 31 KB | Body = Loading... Has canonical |
| 7 | `out/resources/roas-is-not-a-number-its-a-range.html` | `/resources/roas-is-not-a-number-its-a-range` | 31 KB | Body = Loading... Has canonical |
| 8 | `out/resources/attribution-methods-answer-different-questions.html` | `/resources/attribution-methods-answer-different-questions` | 31 KB | Body = Loading... Has canonical |
| 9 | `out/resources/confidently-defend-budget-shift.html` | `/resources/confidently-defend-budget-shift` | 31 KB | Body = Loading... Has canonical |
| 10 | `out/book-demo.html` | `/book-demo` | 27 KB | No canonical, no JSON-LD |
| 11 | `out/book-demo/thank-you.html` | `/book-demo/thank-you` | 47 KB | No noindex |
| 12 | `out/Login.html` | `/Login` | 27 KB | No noindex |
| 13 | `out/signup.html` | `/signup` | 27 KB | No noindex |
| 14 | `out/404.html` | `/404` | 26 KB | Auto-generated |
| 15 | `out/_not-found.html` | `/_not-found` | 26 KB | Internal Next.js |

---

## 10. Route Inventory — Public Static (`marketing/public/`)

| # | Public Path | Served URL | Type |
|---|---|---|---|
| 1 | `public/implementations/agent-a/index.html` | `/implementations/agent-a/` | Standalone HTML |
| 2 | `public/implementations/agent-b/index.html` | `/implementations/agent-b/` | Standalone HTML |
| 3 | `public/implementations/agent-c/index.html` | `/implementations/agent-c/` | Standalone HTML |
| 4 | `public/implementations/agent-d/index.html` | `/implementations/agent-d/` | Standalone HTML |
| 5 | `public/implementations/agent-e/index.html` | `/implementations/agent-e/` | Standalone HTML |
| 6 | `public/implementations/population-manifest.json` | `/implementations/population-manifest.json` | JSON |
| 7 | `public/implementations/README.md` | `/implementations/README.md` | Markdown |

---

## 11. Production Route Probes

From the audit report (2026-05-20):

| URL | Status | Notes |
|---|---|---|
| `https://skeldir.com/` | 200 | Hero content present. Server: Netlify |
| `https://skeldir.com/product` | 200 | No canonical |
| `https://skeldir.com/resources/why-your-attribution-numbers-never-match` | 200 | Body = Loading... for all UAs |
| `https://skeldir.com/robots.txt` | 404 | |
| `https://skeldir.com/sitemap.xml` | 404 | |
| `https://skeldir.com/llms.txt` | 404 | |
| `https://skeldir.com/privacy` | 404 | |
| `https://skeldir.com/product?utm_source=test` | 200 | No canonical = parameter pollution |

---

## 12. Stale Clones / Non-Authoritative Directories

| Directory | Status | Notes |
|---|---|---|
| `skeldir-deploy-clean/` | Stale clone | Not the active codebase |
| `skeldir-favicon-clean/` | Stale clone | Contains historical `sitemap.ts` and `robots.ts` (deleted from current marketing/) |
| `skeldir-netlify-fix-20260430/` | Stale clone | Netlify deployment fix dated 2026-04-30 |
| `skeldir-2.0-clone/` | Stale clone | General clone |
| `skeldir-production-main-deploy-20260518/` | Production reference | Has `netlify.toml`, different git remote (Synergyscape-V1) |
| `src/` (at workspace root) | Unknown | Exists at `C:\Users\ayewhy\Skeldir Webpage\src\` outside marketing/ |

---

## 13. Unresolved Production/Dashboard Unknowns

| Unknown | Impact | Resolution |
|---|---|---|
| Netlify dashboard WAF/bot management rules | May block or rate-limit AI bots not visible in repo | Requires Netlify dashboard access |
| `www.skeldir.com` DNS/redirect behavior | May create duplicate content surface | Requires DNS probe |
| Netlify deploy logs and build settings | May have overrides not in netlify.toml | Requires dashboard access |
| Google Search Console verification | Unknown index coverage | Requires GSC access |
| Production analytics (if any) | May exist outside codebase | Requires team confirmation |
| Cal.com booking attribution chain | UTM forwarding unverified | Requires Cal.com dashboard |

---

*Generated: 2026-05-21 | Phase: D0 | Status: Evidence frozen*
