# Export CSV compatibility and authority lifecycle

## Authority hierarchy

This document is **subordinate** to the B2.5-P11 phase contract. Where a
compatibility promise and a P11 authority requirement cannot both hold on the
same wire shape, P11 authority honesty wins and the compatibility obligation is
discharged through an explicit, versioned surface lifecycle -- never through a
documented carve-out.

```text
P11-G4 authority honesty          (highest)
  > CSV surface/version lifecycle
  > positional convenience for a specific historical shape
```

The governing threshold is P11-G4: a CSV or XLSX display export must carry
either an `envelope_ref` or a non-authoritative display label **inside the
artifact**, because a downloaded file is detached from its URL, query string,
headers, and media type. A local compatibility policy cannot grant an exemption
from it.

## Why `legacy-v1` was retired

`legacy-v1` emitted exactly:

```text
date,channel,revenue,conversions,confidence
```

There is a real information-theoretic conflict here: those five columns are
fully consumed by data, so the shape cannot carry an authority classification
without either changing the positional contract or adding a preamble/metadata
row (which is forbidden -- CSV must stay rectangular and header-first).

Retaining it as the default meant every ordinary download produced a file that
could not state whether its numbers were verified trust or display convenience.
That is precisely the ambiguity P11 exists to remove, so the profile is
**retired** rather than emitted.

Retirement is explicit and discoverable at runtime, not silent:

```text
GET /api/export/csv?csv_schema_version=legacy-v1
GET /api/export/revenue?format=csv&csv_schema_version=legacy-v1

-> HTTP 410
   {"detail": {"status": "refused",
               "reason_code": "legacy_csv_profile_retired",
               "retired_profile": "legacy-v1",
               "replacement_profile": "b25-p11-export-csv-compat-v1"}}
```

The refusal names its replacement, so a caller discovers the migration path from
the response itself.

## Active profiles

### `b25-p11-export-csv-compat-v1` (default)

Media type
`text/csv; profile="https://api.skeldir.com/profiles/export-csv-compat-v1"`.

```text
date,channel,revenue,conversions,confidence,projection_authority,projection_schema_version
```

This profile resolves the conflict rather than choosing a side:

* **Positional compatibility is preserved.** Indices 0-4 are the original five
  legacy columns, in the original order, with the original values. Any consumer
  reading by positional index is completely unaffected.
* **P11-G4 is satisfied.** Every data record carries
  `non_authoritative_display` and the profile version at indices 5-6, so the
  classification survives detachment.
* **No preamble.** The file stays rectangular and header-first.

The only consumers affected are those that assert an exact column *count*
rather than reading by index. That break is explicit, versioned, contract-
declared, and covered by the 410 migration path above.

### `b25-p11-export-csv-v2` (opt-in)

Media type `text/csv; profile="https://api.skeldir.com/profiles/export-csv-v2"`.

```text
projection_authority,projection_schema_version,date,channel,revenue,conversions,confidence
```

Authority-first ordering, for consumers that prefer the classification in the
leading columns. Unchanged by the third corrective, so anyone who already
adopted it sees no wire change.

## Universal invariant

Every **active** CSV profile must satisfy P11-G4. This is enforced as a
hierarchy-aware property test that iterates the supported profile set rather
than a hand-picked profile, so a newly added profile that cannot identify its
own authority class fails CI automatically
(`test_every_active_csv_profile_satisfies_p11_g4`). A compliant opt-in profile
never compensates for a noncompliant default
(`test_default_request_emits_self_identifying_detached_csv`).

## Versioning

The authoritative export contract advances to 4.x and the aggregate Export
OpenAPI to 5.0.0 for the profile retirement and the new default. Historical
baselines are never rewritten to bless later wire shapes.
