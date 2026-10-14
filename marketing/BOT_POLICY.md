# Skeldir — Bot Policy (Phase D3)

This document is the human-readable companion to `discoverability.bot-policy.json`. **The JSON manifest is authoritative** for automation (`npm run discoverability:d3`). If they disagree, fix the JSON and regenerate or adjust `src/app/robots.ts` (which imports the manifest).

## Purpose

Separate **live retrieval / search visibility** from **model-training and bulk reuse**, without using `robots.txt` as a security boundary. Static export means every client receives the same HTML bytes; user-agent curls prove **parity**, not **identity** (see `identity_verification_limits` in the manifest).

## Tier model

| Tier | Meaning | Robots stance (summary) |
|------|---------|-------------------------|
| tier1_search_index_retrieval | Search and answer-engine style automatic retrieval | Explicit `Allow: /` where `robots_required` |
| tier2_user_triggered_fetch | User-directed fetchers | Documented; may omit dedicated robots rows (`robots_required: false`) per operator guidance |
| tier3_training_bulk_reuse | Training, corpus, or broad reuse | Default `Disallow: /` for Skeldir-chosen operators (explicit product decision) |
| tier4_unknown_or_secondary | Ambiguous or low-signal | `defer` or `monitor_only`; often inherit `User-agent: *` |

## Operator decisions (current)

- **Allow retrieval:** `Googlebot`, `Bingbot`, `Googlebot-Image`, `OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, `Claude-User` (Anthropic documents robots obedience for user-directed access).
- **User-triggered (robots secondary signal):** `ChatGPT-User` — `robots_required: false` per OpenAI’s distinction from automatic crawlers; still parity-tested locally.
- **Disallow training / bulk (robots):** `GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`.
- **Defer / monitor:** `Applebot`, `GoogleOther`, `Meta-ExternalAgent`, `facebookexternalhit`, `OAI-AdsBot`, `Perplexity-User` — see manifest `risk_note` and `confidence`.

## D2 / production governance

`discoverability.bot-policy.json` includes `d2_dependency`. **D3 production-final** remains blocked until D2 is merged, CI-green on `main`, and deploy/preview evidence exists — even when D3 local harness passes.

## llms.txt

Out of scope for D3 (manifest `llms_txt_scope`). Do not treat `/llms.txt` as a substitute for this policy.

## Review

Default owner: **Skeldir web platform / growth**. Review manifest `review_interval_days` per bot; default 90 days unless overridden.

## Commands

```bash
npm run build
npm run discoverability:d3
npm run discoverability:d3:negative-controls
```

Optional deploy evidence: set `D3_LIVE_URL` to `https://skeldir.com` or a Netlify preview origin, then re-run `npm run discoverability:d3`.
