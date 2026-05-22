# Entity Profile Registry — Skeldir (Phase D4)

External profiles considered for `Organization.sameAs` in JSON-LD. **Only verified, owned profiles belong here.**

Machine-readable list: `marketing/entity-profile-registry.json` (`sameAs` string array). This document is the human audit trail.

## Policy

| Field | Rule |
|-------|------|
| profile_url | HTTPS URL of the public profile |
| platform | e.g. LinkedIn, X |
| ownership proof | Link to internal evidence or PR that proves control |
| HTTP status | 200 (or documented redirect chain) |
| included_in_sameAs | `true` only when verified |
| last_verified | ISO date |
| owner | Team / individual responsible |

## Verified profiles

| profile_url | platform | Verified? | Included in sameAs? | Evidence | Owner |
|-------------|----------|-----------|----------------------|----------|-------|
| *(none yet)* | — | no | no | Add rows when profiles are live and ownership is proven | — |

When the first profile is verified:

1. Add a row here with evidence and `included_in_sameAs: true`.
2. Add the same URL to `entity-profile-registry.json` under `sameAs`.
3. Re-run `npm run discoverability:d4`.
