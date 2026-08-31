# Status Surface Registry

Machine-readable source: `discoverability.status-registry.json`

| Field | Value |
|---|---|
| Route | `/status` |
| Current public state | `no_incidents_reported` |
| Active incidents | _(none)_ |
| Scheduled maintenance | _(none)_ |
| Status update mode | `manual` |
| Last reviewed | `2026-02-25` |
| Owner | Skeldir Infrastructure |
| Operator contact | `support@skeldir.com` |
| Indexable | yes |
| Sitemap required | yes |

## Approved operational claims

The public `/status` page may use only these operational phrases (or close paraphrases validated by `d6-status-exposure.mjs`):

- no active incidents
- no service degradations currently reported
- manual status declaration
- not an automated real-time feed
- affected operators
- scheduled maintenance

## Not approved (must not appear on `/status`)

- fully operational
- all systems operational
- processing normally
- SLA / uptime guarantees
- real-time automated feed
- 99.9% uptime

Update `discoverability.status-registry.json` before changing incident/maintenance copy on the live page.
