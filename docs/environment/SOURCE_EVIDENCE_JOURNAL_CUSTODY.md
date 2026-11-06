# Source-Evidence Journal Custody

## Scope

The XXV source-evidence journal is the authentication root's record of every
signed provider source fact. It is outside the financial database principal's
control. A container volume or a configured path is **not** by itself a
production custody boundary: the storage, writer identity, deletion authority,
retention and restore target must all be separately governed.

## Supported production topology

| Element | Requirement |
|---|---|
| Live journal | Encrypted EFS access point (or equivalent durable POSIX storage) mounted read-write only in `auth_ingress`; mounted read-only in API and observer; **not mounted** in DB, beat, relay, publisher or any financial-maintenance worker. |
| Writer custody | POSIX owner is the authentication-root UID. API/observer have no write permission. The database maintenance principal has no filesystem mount and no IAM permission on the access point. |
| Custody archive | S3 bucket with Object Lock in COMPLIANCE mode (minimum 365 days), versioning, SSE-KMS and public-access block. Only the custody/observer role may `PutObject`; no runtime or maintenance role may delete or overwrite. |
| Archive object | `source-evidence-<tip>.jsonl` plus a signed `source-evidence-<tip>.manifest.json`. The manifest is signed by the Ed25519 history-witness/custody key, which is mounted only in the observer/custody task. |
| Retention | Object Lock prevents overwrite/deletion for the retention period. EFS backup/AWS Backup retains the live volume; archive objects are never replaced with a different tip. |
| Restore | Provision an empty live access point, restore the newest verified bundle, start the auth root, and let the observer verify the signed checkpoint prefix before readers resume. |

The live EFS and S3 Object Lock resources are deployment resources. This
repository contains the signed bundle format, verifier, restore guard and
tests; it does not provision or apply those AWS resources, and no AWS
execution is claimed here.

## Operations

Export (observer/custody task, never a financial-maintenance worker):

```text
python scripts/ops/source_journal_custody.py export \
  --journal "$B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH" \
  --custody-dir /mnt/custody/source-evidence \
  --private-key "$B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"
```

`--custody-dir` must be a mounted local path. An object-store URI such as
`s3://bucket/prefix` is refused with
`custody_object_store_adapter_unavailable`; this CLI does not silently write a
local directory named `s3:`. Object-store upload and Object Lock enforcement
are the deployment adapter's responsibility; the bundle bytes and manifest
signature are produced and verified identically once mounted.

Capture opens the writer's existing `.lock` sidecar read-only and takes a
shared OS lock. It never creates or writes the sidecar, the journal, or the
live directory, so the observer can run with the documented read-only journal
mount. A missing sidecar on a non-empty journal is refused
(`source_journal_lock_missing`) rather than creating one. An empty journal may
be exported as the empty prefix without a sidecar.

If a previous publication left tip-named bytes without a manifest, retry
completes the publication only when those bytes are byte-identical to the
captured live prefix. A planted, stale, or substituted orphan is refused with
`custody_bundle_substitution`; it never receives a custody signature.

Verify:

```text
python scripts/ops/source_journal_custody.py verify \
  --manifest <manifest.json> \
  --public-key "$B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"
```

Restore (new/empty live path only, or a live path that is a prefix of the
archive):

```text
python scripts/ops/source_journal_custody.py restore \
  --manifest <manifest.json> \
  --journal "$B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH" \
  --public-key "$B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH" \
  --witness-journal "$B26_P2_HISTORY_WITNESS_JOURNAL_PATH" \
  --witness-public-key "$B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH"
```

The witness journal is the independent accepted commitment. The CLI verifies
it and refuses a bundle whose verified prefix is below the latest accepted
source count/tip (`custody_restore_below_accepted_commitment`). An operator
may instead pass `--accepted-source-count` and `--accepted-source-tip` from a
separately verified witness record. Supplying neither is allowed only for
non-production recovery drills.

Restore returns `restored`, `restored_prefix`, `already_current` or
`live_is_newer`. It leaves the live journal untouched when the live chain
already contains the archived prefix plus later committed facts, and it
refuses `custody_restore_diverged` rather than deleting committed history.

## Failure scope

- A torn final line is repaired under the journal lock before appends; the
  committed prefix and chain remain intact.
- A lost live volume is recovered from the newest verified bundle; records are
  not regenerated or guessed.
- A redeploy with an empty live mount restores before the auth root accepts
  new facts.
- A stale archive cannot overwrite a newer live chain.
- A restore below the independently accepted witness prefix is refused; the
  accepted commitment is never reset to bless missing facts.
- A corrupt bundle, wrong key, altered manifest, count/tip mismatch or
  divergent live chain is refused.
- A valid older signed bundle relocated under the current snapshot name is
  refused with `custody_bundle_identity_mismatch`; success requires the
  manifest tip to match its filename and the bundle bytes to equal the
  captured live prefix.

## Limits

- The signed bundle proves the archived journal bytes and tip; it does not
  make the S3/EFS deployment exist.
- Object Lock retention, KMS grants, EFS access-point IAM and task mounts must
  be audited in the deployment account.
- The history witness checkpoint remains the independent signed authority over
  the journal tip; the archive is the durable copy used for restore.
