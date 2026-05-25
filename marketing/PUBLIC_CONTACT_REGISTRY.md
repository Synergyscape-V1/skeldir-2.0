# Public Contact Registry

Machine-readable source: `discoverability.public-contacts.json`

| Type | Email | Rendered on public pages | Purpose |
|---|---|---|---|
| privacy | engineering@skeldir.com | yes | Primary on `/privacy` (privacy posture inquiries) |
| press | press@skeldir.com | yes | Media and analyst inquiries |
| security_engineering | engineering@skeldir.com | yes | Security/technical routing from press |
| sales | sales@skeldir.com | yes | Commercial and procurement |
| security | security@skeldir.com | yes | Primary on `/security` |
| support | support@skeldir.com | yes | Primary on `/status` |
| careers | engineering@skeldir.com | yes | Primary on `/careers` (talent inquiries) |
| integration | sales@skeldir.com | yes | Primary on `/api` (integration agreements) |

Public pages may render only contacts with `publicly_rendered: true`. The D6-b harness validates rendered `mailto:` and plain-text emails against this registry and route-specific registries (`discoverability.careers-registry.json`, etc.).
