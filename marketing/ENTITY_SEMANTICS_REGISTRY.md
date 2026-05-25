# Entity Semantics Registry — Skeldir (Phase D4)

This registry is the **canonical public semantic contract** for Skeldir marketing HTML, metadata, and JSON-LD. It governs what the site may claim as primary truth.

## Canonical name

**Skeldir**

## Short description (metadata / OG fallback)

Skeldir reconciles platform-reported ad revenue with verified commerce and payment evidence so teams and AI agents work from audit-ready financial truth—not dashboard guesses.

## Long canonical definition

Skeldir is deterministic revenue-verification and attribution infrastructure that reconciles platform-reported revenue against verified commerce/payment evidence and exposes audit-ready financial truth through TrustEnvelopes.

## Approved terminology

- Revenue verification, verified commerce/payment evidence, deterministic reconciliation
- Attribution infrastructure, audit-ready financial truth, TrustEnvelopes (when referring to the product concept; public proof pages remain D5)
- Platform-reported vs verified revenue, confidence ranges (when visibly explained on the page)

## Disallowed or high-risk terminology (as *primary* positioning without visible support)

- Claiming regulatory status, “financial product,” or legal audit sign-off without D5 proof surfaces
- Presenting Skeldir as generic “decision intelligence” **without** tying claims to reconciliation/verification visible on the page
- Invented `sameAs` URLs or unverified social/wiki profiles

## Page-level messaging map

| Public route | Primary visible intent | JSON-LD primary types |
|--------------|------------------------|------------------------|
| `/` | Homepage hero + subheads | `Organization`, `WebSite`, `WebPage` |
| `/product` | Product hero + capabilities | `SoftwareApplication`, `WebPage` |
| `/pricing` | Plans and pricing narrative | `WebPage` only (no standalone `Offer` on this route) |
| `/agencies` | Agency positioning | `WebPage` |
| `/resources` | Article index | `CollectionPage`, `BreadcrumbList` |
| `/resources/<slug>` | Long-form article | `Article`, `BreadcrumbList` |

## Schema `@id` strategy

- Organization: `{SITE_ORIGIN}/#organization` (from `src/lib/crawlUrls.ts` → `SITE_ORIGIN`)
- WebSite: `{SITE_ORIGIN}/#website`
- Route-scoped nodes: `{canonicalUrl(path)}#fragment` (e.g. `#webpage`, `#article`, `#collection`, `#software`)

## Publisher / organization identity

Single Organization node emitted on the homepage; other pages reference `publisher: { "@id": "{SITE_ORIGIN}/#organization" }` where applicable.

## Logo / image strategy

- Organization / publisher logo URL: `{SITE_ORIGIN}/images/skeldir-logo-black.png` (must be crawlable static asset)
- Article `image`: hero image absolute URL per `articlesData`

## `sameAs` policy

- Only URLs listed in `entity-profile-registry.json` with verified ownership may appear in `Organization.sameAs`.
- If the registry `sameAs` array is empty, **omit** `sameAs` from JSON-LD (do not emit an empty array in production payloads).

## Machine-readable registry (D6-C)

Harness scanners consume **`entity-semantics-registry.json`** (canonical name, approved/disallowed/high-risk terminology, route exceptions). D6 evidence routes are scanned on title, meta description, H1, BLUF, Key Facts, the first 30% of `<main>`, and JSON-LD name/description fields.
