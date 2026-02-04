BEGIN;

SET LOCAL row_security = off;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO public.tenants (
    id,
    name,
    api_key_hash,
    notification_email,
    created_at,
    updated_at
) VALUES
    (
        '00000000-0000-0000-0000-0000000000a1',
        'B060 E2E Tenant A',
        '65fc9e6eb7328887be362dde01874ebb88dd83d2071bcbe03b1318ad6a3063d3',
        'b060-e2e-tenant-a@invalid.example',
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    ),
    (
        '00000000-0000-0000-0000-0000000000b1',
        'B060 E2E Tenant B',
        '9fb4e9792ea2a445a4de761ce9585d251c484caa13906c96fa79e97d06520621',
        'b060-e2e-tenant-b@invalid.example',
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    )
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    api_key_hash = EXCLUDED.api_key_hash,
    notification_email = EXCLUDED.notification_email,
    updated_at = EXCLUDED.updated_at;

INSERT INTO public.platform_connections (
    id,
    tenant_id,
    platform,
    platform_account_id,
    status,
    connection_metadata,
    created_at,
    updated_at
) VALUES
    (
        '10000000-0000-0000-0000-0000000000a1',
        '00000000-0000-0000-0000-0000000000a1',
        'stripe',
        'acct_e2e_a',
        'active',
        NULL,
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    ),
    (
        '10000000-0000-0000-0000-0000000000a2',
        '00000000-0000-0000-0000-0000000000a1',
        'dummy',
        'dummy_e2e_a',
        'active',
        NULL,
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    ),
    (
        '10000000-0000-0000-0000-0000000000b1',
        '00000000-0000-0000-0000-0000000000b1',
        'stripe',
        'acct_e2e_b',
        'active',
        NULL,
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    ),
    (
        '10000000-0000-0000-0000-0000000000b2',
        '00000000-0000-0000-0000-0000000000b1',
        'dummy',
        'dummy_e2e_b',
        'active',
        NULL,
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    )
ON CONFLICT (tenant_id, platform, platform_account_id) DO UPDATE SET
    status = EXCLUDED.status,
    connection_metadata = EXCLUDED.connection_metadata,
    updated_at = EXCLUDED.updated_at;

INSERT INTO public.platform_credentials (
    id,
    tenant_id,
    platform_connection_id,
    platform,
    encrypted_access_token,
    encrypted_refresh_token,
    expires_at,
    scope,
    token_type,
    key_id,
    created_at,
    updated_at
) VALUES
    -- Note: E2E requires PLATFORM_TOKEN_ENCRYPTION_KEY=e2e-platform-key to decrypt tokens at runtime.
    (
        '20000000-0000-0000-0000-0000000000a1',
        '00000000-0000-0000-0000-0000000000a1',
        '10000000-0000-0000-0000-0000000000a1',
        'stripe',
        pgp_sym_encrypt('stripe-token-a', 'e2e-platform-key'),
        NULL,
        TIMESTAMPTZ '2030-01-01T00:00:00Z',
        NULL,
        'bearer',
        'e2e-key',
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    ),
    (
        '20000000-0000-0000-0000-0000000000a2',
        '00000000-0000-0000-0000-0000000000a1',
        '10000000-0000-0000-0000-0000000000a2',
        'dummy',
        pgp_sym_encrypt('dummy-token-a', 'e2e-platform-key'),
        NULL,
        TIMESTAMPTZ '2030-01-01T00:00:00Z',
        NULL,
        'bearer',
        'e2e-key',
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    ),
    (
        '20000000-0000-0000-0000-0000000000b1',
        '00000000-0000-0000-0000-0000000000b1',
        '10000000-0000-0000-0000-0000000000b1',
        'stripe',
        pgp_sym_encrypt('stripe-token-b', 'e2e-platform-key'),
        NULL,
        TIMESTAMPTZ '2030-01-01T00:00:00Z',
        NULL,
        'bearer',
        'e2e-key',
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    ),
    (
        '20000000-0000-0000-0000-0000000000b2',
        '00000000-0000-0000-0000-0000000000b1',
        '10000000-0000-0000-0000-0000000000b2',
        'dummy',
        pgp_sym_encrypt('dummy-token-b', 'e2e-platform-key'),
        NULL,
        TIMESTAMPTZ '2030-01-01T00:00:00Z',
        NULL,
        'bearer',
        'e2e-key',
        TIMESTAMPTZ '2026-02-03T00:00:00Z',
        TIMESTAMPTZ '2026-02-03T00:00:00Z'
    )
ON CONFLICT (tenant_id, platform, platform_connection_id) DO UPDATE SET
    encrypted_access_token = EXCLUDED.encrypted_access_token,
    encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
    expires_at = EXCLUDED.expires_at,
    scope = EXCLUDED.scope,
    token_type = EXCLUDED.token_type,
    key_id = EXCLUDED.key_id,
    updated_at = EXCLUDED.updated_at;

COMMIT;
