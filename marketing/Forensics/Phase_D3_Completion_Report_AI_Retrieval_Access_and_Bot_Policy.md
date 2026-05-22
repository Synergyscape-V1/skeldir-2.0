# Phase D3 Completion Report — AI Retrieval Access and Bot Policy

**Date:** 2026-05-22  
**Repository:** `Synergyscape-V1/skeldir-2.0` (remote), workspace `Skeldir Webpage` — application code under `marketing/`  
**Branch:** `feat/discoverability-remediation`  
**Commit:** `a410242a` — `feat(discoverability): Phase D3 bot policy, robots compiler, and parity harness`  
**Merge to remote `main`:** **Not completed** — GitHub reports *“feat/discoverability-remediation has no history in common with main”* (`gh pr create` fails). Reconciling the marketing-site branch with `main` requires a planned history merge, subtree, or moving the marketing app onto the same root commit as `main` before a protected-branch PR can land.

## 1. Verdict

**PARTIAL**

- **D3 local proof state:** **PASS** — `npm run discoverability:d3` and `npm run discoverability:d3:negative-controls` succeed; `out/robots.txt` matches `discoverability.bot-policy.json`; static-server UA fetches show real HTML on required URLs.
- **D3 production-final state:** **BLOCKED** — `d2_dependency.d3_production_final_blocked_by_d2` remains `true` until D2 main merge, required checks on `main`, and deploy/preview proof close (per embedded manifest notes and prior D2-C2 report).

## 2. Scope Confirmation

This report claims **Phase D3 only** (bot policy matrix, robots alignment, retrieval parity harness, negative controls, D2-aware governance). **No** completion claims for D4, D5, D6, D9, or `llms.txt` rollout.

## 3. D2 Dependency Status

| Item | State |
|------|--------|
| D2 local mechanism | PASS (D2 harness re-run after `validateRobotsPolicy` refinement) |
| D2 main / CI integration | BLOCKED (historical PR friction documented in D2-C2 forensics; resolve via normal PR into `main`) |
| D2 deploy / preview proof | BLOCKED (no origin attached in this iteration) |
| D3 production-final blocked by D2? | **yes** |

## 4. Files Changed

| File | Change | Reason |
|------|--------|--------|
| `marketing/discoverability.bot-policy.json` | **New** | Machine-readable bot matrix, D2 release metadata, D3 fetch suite patterns |
| `marketing/BOT_POLICY.md` | **New** | Human policy summary + tier semantics |
| `marketing/src/app/robots.ts` | **Update** | Compile `robots.txt` from manifest (disallow training bots; allow retrieval bots; wildcard last) |
| `marketing/scripts/discoverability/lib/d3-bot-policy.mjs` | **New** | Schema validation, robots parse/align, sensitive `Disallow` scan |
| `marketing/scripts/discoverability-d3-harness.mjs` | **New** | `npm run discoverability:d3` — build, D2 robots hygiene, alignment, UA fetch matrix, optional `D3_LIVE_URL` |
| `marketing/scripts/discoverability-d3-negative-controls.mjs` | **New** | `npm run discoverability:d3:negative-controls` |
| `marketing/package.json` | **Update** | Added `discoverability:d3` scripts |
| `marketing/scripts/discoverability/lib/d2-crawl-graph.mjs` | **Update** | `validateRobotsPolicy`: blanket `Disallow: /` only forbidden under `User-agent: *` (allows per-bot training `Disallow: /` required by D3) |
| `.github/workflows/marketing-discoverability.yml` | **New** | CI: discoverability D2 + D3 + D3 negative (no full-repo ESLint; see §10) |

## 5. Bot Policy Matrix Summary

Full detail: `discoverability.bot-policy.json`. Abbreviated:

| Bot | Operator | Tier | Policy | Robots? | Source (canonical doc) | Last Verified | Confidence | Owner |
|-----|----------|------|--------|---------|-------------------------|---------------|------------|--------|
| Googlebot | Google | tier1 | allow | yes | developers.google.com/search/docs/crawling-indexing/googlebot | 2026-05-22 | high | Skeldir web platform / growth |
| Bingbot | Microsoft | tier1 | allow | yes | bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0 | 2026-05-22 | high | Skeldir web platform / growth |
| OAI-SearchBot | OpenAI | tier1 | allow | yes | platform.openai.com/docs/bots | 2026-05-22 | high | Skeldir web platform / growth |
| ChatGPT-User | OpenAI | tier2 | allow | no | platform.openai.com/docs/bots | 2026-05-22 | medium | Skeldir web platform / growth |
| GPTBot | OpenAI | tier3 | disallow | yes | platform.openai.com/docs/bots | 2026-05-22 | high | Skeldir web platform / growth |
| Claude-SearchBot | Anthropic | tier1 | allow | yes | support.anthropic.com/en/articles/8896518-what-is-claude-bot | 2026-05-22 | high | Skeldir web platform / growth |
| Claude-User | Anthropic | tier2 | allow | yes | support.anthropic.com/en/articles/8896518-what-is-claude-bot | 2026-05-22 | high | Skeldir web platform / growth |
| ClaudeBot | Anthropic | tier3 | disallow | yes | support.anthropic.com/en/articles/8896518-what-is-claude-bot | 2026-05-22 | high | Skeldir web platform / growth |
| PerplexityBot | Perplexity | tier1 | allow | yes | docs.perplexity.ai/guides/bots | 2026-05-22 | medium | Skeldir web platform / growth |
| Google-Extended | Google | tier3 | disallow | yes | developers.google.com/search/docs/crawling-indexing/google-common-crawlers | 2026-05-22 | high | Skeldir web platform / growth |
| CCBot | Common Crawl | tier3 | disallow | yes | commoncrawl.org/ccbot | 2026-05-22 | medium | Skeldir web platform / growth |
| (+ defer/monitor bots) | various | tier4 | defer / monitor_only | no | see manifest `source_url` | 2026-05-22 | low–medium | Skeldir web platform / growth |

## 6. Robots Alignment Evidence

- **Generation / validation:** `src/app/robots.ts` imports `discoverability.bot-policy.json` and orders disallow stanzas before allow stanzas, then `User-agent: *` / `Allow: /`. `scripts/discoverability/lib/d3-bot-policy.mjs` recomputes expected UA rules and compares to parsed `out/robots.txt`.
- **Robots excerpt (built):**

```txt
User-Agent: GPTBot
Disallow: /
...
User-Agent: OAI-SearchBot
Allow: /
...
User-Agent: *
Allow: /
Host: skeldir.com
Sitemap: https://skeldir.com/sitemap.xml
```

- **Sitemap line:** `Sitemap: https://skeldir.com/sitemap.xml` (matches `src/lib/crawlUrls.ts` authority).
- **Retrieval allow proof:** Alignment validator + D2 `validateRobotsPolicy` / meta-noindex law.
- **Training / bulk decision proof:** `GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot` each `Disallow: /` in `out/robots.txt`.
- **Sensitive-path leak scan:** `validateRobotsDisallowNoSensitiveLeaks` rejects `/admin`, `/internal`, `/api/`, etc., in any `Disallow`.

## 7. Retrieval Bot Fetch Evidence (local static server)

Harness: `npm run discoverability:d3` section `[6]`. **URLs:** `/`, `/resources`, `/resources/why-your-attribution-numbers-never-match`, `/product`, `/pricing`, `/agencies`. **UAs:** from manifest `include_in_local_static_fetch_matrix` (includes Google smartphone UA string, Bingbot, OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot).

| Check | Result |
|-------|--------|
| HTTP status | 200 for all cells |
| Loading shell heuristic | no match |
| WAF/challenge heuristic | no match |
| Article markers on article URL | match |
| Unexpected `noindex` on article | absent |

## 8. Negative Controls

| ID | Scenario | Expected failure |
|----|----------|------------------|
| NC-D3-01 | Remove `bots` array | Schema errors |
| NC-D3-02 | Remove `gptbot` id | Required id missing |
| NC-D3-03 | Tier3 + `policy: allow` | Tier / policy conflation |
| NC-D3-04 | Tier1 + `policy: disallow` | Tier / policy conflation |
| NC-D3-05 | Synthetic robots block `OAI-SearchBot` | Alignment errors vs manifest |
| NC-D3-06 | Synthetic robots allow `GPTBot` | Alignment errors vs manifest |
| NC-D3-07 | Robots without sitemap | `validateRobotsPolicy` |
| NC-D3-08 | `Disallow: /admin` | Sensitive leak validator |
| Sanity | Golden `out/robots.txt` vs live manifest | zero alignment errors |

## 9. Deployment / Preview Evidence

- **Origin tested:** none in this run (`D3_LIVE_URL` unset).
- **Gate D3.4:** **BLOCKED** pending explicit `D3_LIVE_URL` curls to production or Netlify preview (documented in harness `[7]` skip message).

## 10. Git / CI Proof

- **Push:** `origin/feat/discoverability-remediation` at `4cae3817` (D3 feature `a410242a` plus forensics doc commits).
- **PR to `main`:** **blocked** — `gh pr create --base main --head feat/discoverability-remediation` → *“no history in common with main”* (same blocker class as D2-C2 forensics).
- **Workflow:** `.github/workflows/marketing-discoverability.yml` runs on `push` when `marketing/**` or the workflow file changes.
- **Green CI (feat branch):** run `26310582078` — https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/26310582078 (D2 + D3 + D3 negative controls all passed on `feat/discoverability-remediation`).
- **Note on ESLint:** `npm run lint` still reports long-standing **errors** elsewhere in `marketing/`. The workflow intentionally **does not** gate on full-repo lint so discoverability automation can go green; fixing lint is a separate task.
- **`main` branch:** discoverability workflow will not execute on `main` until this work is merged/rebased onto `main` (or the workflow file exists on `main` from another path).

## 11. Remaining Unknowns

- Live Netlify/WAF behavior for real bot IP ranges (not provable from static export alone).
- Publisher-reported disputes for third-party bots (noted for `PerplexityBot` in manifest).
- Exact future naming for Meta crawlers (`verify_current_status` in manifest).

## 12. D4 Readiness Statement

**D4 may begin** for local/branch work on non–bot-policy topics. Anything requiring **authoritative production `robots.txt` or live bot fetches** remains **blocked** until D2 closes on `main` and `D3_LIVE_URL` evidence is collected.

---

## Remediation summary (initial findings → fixes)

1. **No committed bot matrix** → Added `discoverability.bot-policy.json` + `BOT_POLICY.md`.
2. **Robots drift / GPTBot incorrectly allowed for training class** → `robots.ts` now compiles from JSON; training crawlers get explicit `Disallow: /`.
3. **No machine alignment** → `d3-bot-policy.mjs` + `discoverability:d3`.
4. **No UA matrix from policy** → Fetch list driven by `include_in_local_static_fetch_matrix`.
5. **`validateRobotsPolicy` false positive on training `Disallow: /`** → Scoped blanket-disallow check to `User-agent: *` only (D2/D3 compatible).
