# Append-Only Test Isolation

`attribution_events` is protected truth. M2 keeps append-only triggers and RLS enabled during tests.

Allowed cleanup physics:

- drop disposable database;
- create disposable database from `skeldir_test_template`;
- drop disposable schema;
- drop container volume for local test topology.

Prohibited cleanup physics:

- `DELETE FROM attribution_events` in persistent databases;
- `TRUNCATE attribution_events`;
- disabling append-only triggers;
- disabling RLS;
- using migration-user privileges to bypass runtime truth constraints.

M2 uses `scripts/testing/create_test_template_db.sh` and `scripts/testing/create_disposable_test_db.sh` for speed-conscious isolation. The append-only-sensitive subset is marked `append_only_sensitive`; any legacy test that still documents forbidden cleanup must be quarantined or classified before it can count as a feedback-loop proof.
