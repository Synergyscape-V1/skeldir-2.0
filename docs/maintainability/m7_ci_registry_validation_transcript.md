# M7 CI Registry Validation Transcript

## Coordinate

| Field | Value |
| --- | --- |
| validation_time | 2026-05-19T12:21:07-05:00 |
| branch | `codex/m7-b24-readiness` |
| base_sha | `668fb9867ab973023b8ed4b417a5dcf51489146e` |

## M3 Governance Commands

Command:

```text
python scripts/ci/validate_m3_ci_governance.py --b24-dry-run
```

Observed result:

```text
M3_CI_GOVERNANCE_VALIDATION_PASS
```

Command:

```text
python scripts/ci/validate_m3_ci_governance.py --all
```

Observed result:

```text
M3_CI_GOVERNANCE_VALIDATION_PASS
```

## M4 Operational Runbooks

Command:

```text
python scripts/ci/validate_m4_ops_runbooks.py
```

Observed result:

```text
M4_OPS_RUNBOOK_VALIDATION_PASS
```

The M4 validator checks runbook paths, Make targets, command metadata, host-native drift, queue/task/table references, fixture references, safety language, webhook replay safety, RLS physical proof tokens, runtime proof harness steps, and workflow wiring.

## B2.4 Dry-Run Lane

File:

```text
.github/workflows/b2_4-gate-dry-run.yml
```

M7 wiring added:

```text
make validate-m7-b24-readiness
```

Registry entry added:

```text
docs/ci/enforcer_registry.yaml -> validate-m7-b24-readiness
```

Subsumption entry added:

```text
docs/ci/gate_subsumption_matrix.yaml -> validate-m7-b24-readiness
```

M7 classification: B2.4 gates can continue to enter through the isolated B2.4 governance lane without adding new B2.4 adjudication logic to the monolithic `ci.yml`.
