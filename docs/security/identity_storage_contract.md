# Identity Storage Contract (B1.2-P2)

## Scope

This contract defines identity data allowed at rest for the B1.2 auth substrate:

- `public.users`
- `public.tenant_memberships`
- `public.roles`
- `public.tenant_membership_roles`

Hard requirement: raw email addresses and raw IP addresses MUST NOT be stored in these tables.

## Allowed Identity Fields

### `public.users`

- `id` (`uuid`): opaque internal user identifier (non-PII).
- `login_identifier_hash` (`text`): deterministic hash of canonical login identifier.
- `external_subject_hash` (`text`, nullable): deterministic hash of external IdP subject.
- `auth_provider` (`text`): controlled enum (`password`, `oauth_google`, `oauth_microsoft`, `oauth_github`, `sso`).
- `is_active` (`boolean`): account state.
- `created_at` / `updated_at` (`timestamptz`): audit timestamps.

### `public.tenant_memberships`

- `id` (`uuid`): opaque membership identifier.
- `tenant_id` (`uuid`): tenant scope key.
- `user_id` (`uuid`): FK to `users.id`.
- `membership_status` (`text`): controlled enum (`active`, `revoked`).
- `created_at` / `updated_at` (`timestamptz`): audit timestamps.

### `public.roles`

- `code` (`text`): role key (`admin`, `manager`, `viewer`).
- `description` (`text`): role description.
- `created_at` (`timestamptz`): audit timestamp.

### `public.tenant_membership_roles`

- `id` (`uuid`): opaque assignment identifier.
- `tenant_id` (`uuid`): tenant scope key.
- `membership_id` (`uuid`): FK to membership.
- `role_code` (`text`): FK to `roles.code`.
- `created_at` / `updated_at` (`timestamptz`): audit timestamps.

## Prohibited Identity Fields

The following are prohibited in auth substrate tables:

- Any plaintext email field/value (for example `email`, `user@example.com`)
- Any plaintext IP field/value (for example `ip`, `ip_address`, `192.168.0.1`, IPv6 literals)

## Hash Derivation Rules

`login_identifier_hash` and `external_subject_hash` must be derived with deterministic, peppered hashing:

1. Canonicalize source identifier:
   - trim whitespace
   - lowercase
2. Build material: `"{pepper}:{canonical_identifier}"`
3. Compute `SHA-256` hex digest.
4. Store only digest output in DB.

Pepper requirements:

- Pepper must come from secret management (control-plane managed secret), never hardcoded in production.
- Pepper rotation is forward-only:
  - new writes use current pepper
  - legacy rows remain valid until explicit rehash migration is scheduled.

## Enforcement

- Tenant-scoped auth tables (`tenant_memberships`, `tenant_membership_roles`) must enforce RLS with `app.current_tenant_id`.
- `public.users` must enforce `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`.
- `public.users` access must be self-only (`id = current_setting('app.current_user_id', true)::uuid`) for post-auth reads/updates.
- Runtime roles must not have bypass posture (`rolsuper=false`, `rolbypassrls=false`).
- `public.users` must not contain `tenant_id`; multi-tenant affiliation is encoded only through `tenant_memberships`.
- Pre-auth identity lookup must use the DB-enforced boundary function `auth.lookup_user_by_login_hash(...)` (SECURITY DEFINER, exact hash match, minimal result projection).
- CI must run an auth-substrate PII scan that fails on:
  - prohibited column names (`email`, `ip` families)
  - prohibited value patterns (email/IP literals in stored text/json content)
