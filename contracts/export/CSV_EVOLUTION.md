# Export CSV compatibility policy

The unprofiled `text/csv` response is the immutable legacy-v1 positional
contract:

```text
date,channel,revenue,conversions,confidence
```

Existing callers receive this five-column shape by default. Columns must not be
inserted, removed, reordered, or reinterpreted on that profile.

Callers that need a detached file with explicit display-authority metadata opt
into `csv_schema_version=b25-p11-export-csv-v2`. The response uses media type
`text/csv; profile="https://api.skeldir.com/profiles/export-csv-v2"` and the
following header:

```text
projection_authority,projection_schema_version,date,channel,revenue,conversions,confidence
```

Every v2 data record repeats `non_authoritative_display` and the schema version,
so the classification survives detachment. This is a major contract transition:
the authoritative export contract advances from 2.x to 3.0.0 and the aggregate
Export OpenAPI advances from 3.x to 4.0.0. The historical baseline remains the
original 2.0.0 five-column authority and is never rewritten to bless later wire
shapes.
