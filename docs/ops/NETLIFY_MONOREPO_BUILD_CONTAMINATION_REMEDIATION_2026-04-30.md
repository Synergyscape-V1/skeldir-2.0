# Skeldir Marketing Site Outage Remediation Evidence (2026-04-30)

## Incident Summary

- Incident class: monorepo deployment-boundary contamination affecting Netlify project `skeldir3`.
- Observable symptom: Netlify deploys were triggered by non-marketing `main` merges and failed, creating operational risk to the marketing surface.
- Initial failed evidence anchor: deploy `69f38896ea277f00080fcc76` for merge commit `d658d811c556829557ade0a98cadfaefdc303a74` (B2.3 evidence closeout merge).
- Primary objective: restore deterministic, path-scoped deploy behavior for marketing and preserve favicon correctness.

Reference:
- [Failed deploy 69f38896ea277f00080fcc76](https://app.netlify.com/projects/skeldir3/deploys/69f38896ea277f00080fcc76)

## System-Physics Root Cause Analysis

### Boundary Physics

- The marketing app lives under `marketing/` in a larger monorepo with backend/frontend surfaces.
- Prior to remediation, there was no canonical repo-root `netlify.toml` in `skeldir-2.0-clone` to enforce path-scoped build authority.
- Result: Netlify trigger/build scope was not deterministically constrained by source control policy in-repo.

### Build Failure Physics

- During remediation validation, local reproduction of `marketing` build failed at TypeScript compile due to dev-only files in compile scope:
  - `playwright.config.ts` import of `@playwright/test`
  - Storybook `*.stories.tsx` imports of `@storybook/react`
- This failure mode is independent of runtime marketing code and is caused by TypeScript include surface that captured non-production tooling files.

### Root Cause Verdict

- Confirmed compound mechanism:
  1) deployment trigger scope contamination in monorepo (structural), and
  2) build-compile contamination from dev-only files included in production typecheck (executional).

## Initial Findings (Before Fix)

1. `skeldir-2.0-clone` identified as production-target monorepo for `skeldir3`.
2. No committed canonical `netlify.toml` existed in `skeldir-2.0-clone`.
3. Favicon state drift existed in `marketing/src/app`:
   - stale `favicon.ico` present
   - stale `icon.png`
   - missing `apple-icon.png` and `manifest.webmanifest` alignment
4. Live production endpoint responded `200`, but favicon endpoints reflected old assets:
   - `/icon.png` served large stale binary (`Content-Length: 679257`)
   - `/favicon.ico` returned `200`

## Remediation Executed

## 1) Deploy Boundary Hardening

- Added canonical config: `netlify.toml` at repo root with:
  - `base = "marketing"`
  - `command = "npm run build"`
  - `publish = "out"`
  - `ignore` command using `$CACHED_COMMIT_REF` and `$COMMIT_REF` with path-scoped diff on `marketing/`

Intent:
- backend-only changes should be ignored by Netlify build execution.
- marketing changes should proceed through build/deploy.

## 2) Favicon and Metadata Parity

Aligned `skeldir-2.0-clone` marketing assets/metadata to validated favicon baseline:

- Deleted: `marketing/src/app/favicon.ico`
- Replaced: `marketing/src/app/icon.png`
- Added: `marketing/src/app/apple-icon.png`
- Added: `marketing/src/app/manifest.webmanifest`
- Updated: `marketing/src/app/layout.tsx`
  - canonical PNG icon declarations
  - manifest reference
  - favicon version token advanced to `20260415a`
  - removed `favicon.ico` references

## 3) Production Build Surface Correction

Resolved compile contamination in `marketing/tsconfig.json` by excluding dev-only files from production typecheck:

- `playwright.config.ts`
- `e2e`
- `src/stories`
- `**/*.stories.ts`
- `**/*.stories.tsx`

This converts build scope to runtime-relevant code only.

## Git and PR Evidence

- Remediation branch: `fix/netlify-marketing-boundary-favicon-b23`
- PR: [#426](https://github.com/Synergyscape-V1/skeldir-2.0/pull/426)
- Commits:
  - `db3133564c0831b11e555d12983451d815965006`  
    `fix(marketing): scope Netlify deploys and restore canonical favicons`
  - `ee6a82d129aa2c6fef31a39b9a950e0758c79831`  
    `fix(marketing): exclude dev-only test/story files from Next typecheck`

## Validation Evidence

## A) Build Reproduction and Closure

- Pre-fix local build failures observed:
  - missing `@playwright/test` during Next typecheck (`playwright.config.ts`)
  - missing `@storybook/react` during Next typecheck (`*.stories.tsx`)
- Post-fix local build result: `npm run build` succeeds and static routes generate.

## B) Netlify PR Deploy Signal

- Netlify status context for PR head indicates deploy-preview success:
  - `context: netlify/skeldir3/deploy-preview`
  - `state: SUCCESS`
  - deploy link reported in status checks: `69f3a711beadc00008929ad1`

References:
- [PR 426](https://github.com/Synergyscape-V1/skeldir-2.0/pull/426)
- [Deploy reference 69f3a711beadc00008929ad1](https://app.netlify.com/projects/skeldir3/deploys/69f3a711beadc00008929ad1)

## C) Live Production Probe (Current)

- `https://skeldir3.netlify.app` returns `HTTP 200`.
- Current production favicon endpoints still reflect pre-merge assets (expected until PR merge):
  - `/icon.png` `Content-Length: 679257`
  - `/apple-icon.png` `Content-Length: 5867`
  - `/favicon.ico` `HTTP 200`

## D) Local Asset Fingerprints (Post-remediation source)

- `marketing/src/app/icon.png` SHA256:  
  `57FCF8B51A978607B6A3FA408F02D418307E1CA4975EC89878F6A3985B6740FE`
- `marketing/src/app/apple-icon.png` SHA256:  
  `469E934EF2669232D155753A3E67169DBDDDE371A81F470A6B20814C7055A29C`

## Current Closure Status

- Structural remediation implemented and pushed to PR branch.
- Build contamination resolved locally with successful production build.
- Netlify deploy-preview status reports success for latest PR head.
- Production redeploy of these exact changes is pending merge of PR #426 due required branch protection checks on `main`.

## Post-Merge Verification Checklist (Operational Gate)

1. Merge PR #426 to `main`.
2. Confirm new production deploy for merged commit is successful in Netlify.
3. Re-probe:
   - `https://skeldir3.netlify.app` -> `200`
   - `/icon.png` reflects new binary (not legacy `679257` bytes)
   - `/apple-icon.png` reflects new binary
   - `/favicon.ico` behavior aligns with policy (expected no stale scaffold route)
4. Trigger-scope verification:
   - backend-only commit -> ignored/skipped build for marketing surface
   - marketing-only commit -> successful deploy

## Regression Scope Statement

- No backend service logic, API contracts, Celery, or PostgreSQL schema files were modified.
- Remediation touches only:
  - Netlify deployment config authority
  - marketing favicon/metadata assets
  - marketing TypeScript build-scope exclusions for dev-only files
