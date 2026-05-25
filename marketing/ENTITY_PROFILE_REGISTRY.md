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

## Entity authority waiver (D4-C2)

When fewer than two verified `sameAs` URLs exist, `entity-profile-registry.json` may include:

```json
"entityAuthorityWaiver": { "active": true, "scope": "...", "statement": "...", "operatorAcknowledgedAt": "..." }
```

`npm run discoverability:d4` **fails** if `sameAs` has fewer than two entries **and** `entityAuthorityWaiver.active` is not `true`. This prevents silent “empty sameAs” production closure without an explicit operator decision.

Growth/Ops should replace this waiver by verifying profiles and filling `sameAs`, then setting `entityAuthorityWaiver.active` to `false` or removing the object.

## Verified profiles

| profile_url | platform | Verified? | Included in sameAs? | Evidence | Owner |
|-------------|----------|-----------|----------------------|----------|-------|
| *(none yet)* | — | no | no | Add rows when profiles are live and ownership is proven | — |

## Waiver record (current)

| Field | Value |
|-------|--------|
| status | **active** — see `entity-profile-registry.json` → `entityAuthorityWaiver` |
| reason | No verified LinkedIn/GitHub (or other) URLs have been supplied yet; agent must not invent URLs. |
| next step | Add two verified URLs to `sameAs` and this table, then deactivate the waiver. |

When the first profile is verified:

1. Add a row under **Verified profiles** with evidence and `included_in_sameAs: true`.
2. Add the same URL to `entity-profile-registry.json` under `sameAs`.
3. Re-run `npm run discoverability:d4`.