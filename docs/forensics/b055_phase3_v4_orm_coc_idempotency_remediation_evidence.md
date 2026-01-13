# B0.5.5 Phase 3 v4 ORM/CoC/Idempotency Remediation Evidence

## Repo Pin
```
branch: b055-phase3-v4-orm-coc-idempotency
HEAD: f2ca8136c529e714f295e5ff851026710aeec89c
status:
(clean)
```

## 3.1 PR Head SHA + CI Run (baseline)
- PR: <pending>
- PR head SHA: <pending>
- CI run: <pending>

## 3.2 ORM constraint mismatch (baseline)
### Migration unique constraint
File: alembic/versions/004_llm_subsystem/202601131610_add_llm_api_call_idempotency.py
```
op.create_unique_constraint(
    "uq_llm_api_calls_tenant_request_endpoint",
    "llm_api_calls",
    ["tenant_id", "request_id", "endpoint"],
)
```

### ORM model (LLMApiCall __table_args__)
File: backend/app/models/llm.py
```
__table_args__ = (
    CheckConstraint("input_tokens >= 0", name="ck_llm_api_calls_input_tokens_positive"),
    CheckConstraint("output_tokens >= 0", name="ck_llm_api_calls_output_tokens_positive"),
    CheckConstraint("cost_cents >= 0", name="ck_llm_api_calls_cost_cents_positive"),
    CheckConstraint("latency_ms >= 0", name="ck_llm_api_calls_latency_ms_positive"),
)
```

## 3.3 Idempotency + parity coverage (baseline)
### Idempotency tests currently present
File: backend/tests/test_b055_llm_worker_stubs.py
```
async def test_llm_route_idempotency_prevents_duplicate_audit_rows(test_tenant):
    ...
```
No explicit explanation idempotency test present.

### Parity test scope (constraints not checked)
File: backend/tests/test_b055_llm_model_parity.py
```
for col_name, db_col in db_columns.items():
    model_col = model_columns[col_name]
    assert _normalize_type(db_col["type"]) == _normalize_type(model_col.type)
    assert db_col["nullable"] == model_col.nullable
    db_has_default = db_col["default"] is not None
    model_has_default = model_col.server_default is not None
    assert db_has_default == model_has_default
```

## Hypotheses
- H-ORM-1: TRUE (parity test ignores constraints; ORM missing UniqueConstraint)
- H-COC-1: TRUE (evidence not yet pinned to PR head SHA)
- H-IDEMP-1: TRUE (idempotency implemented but no explanation-specific test)

## Remediation (v4)
### ORM constraint parity applied
File: backend/app/models/llm.py
```
__table_args__ = (
    CheckConstraint("input_tokens >= 0", name="ck_llm_api_calls_input_tokens_positive"),
    CheckConstraint("output_tokens >= 0", name="ck_llm_api_calls_output_tokens_positive"),
    CheckConstraint("cost_cents >= 0", name="ck_llm_api_calls_cost_cents_positive"),
    CheckConstraint("latency_ms >= 0", name="ck_llm_api_calls_latency_ms_positive"),
    UniqueConstraint(
        "tenant_id",
        "request_id",
        "endpoint",
        name="uq_llm_api_calls_tenant_request_endpoint",
    ),
)
```

### Explanation idempotency test added
File: backend/tests/test_b055_llm_worker_stubs.py
```
async def test_llm_explanation_idempotency_prevents_duplicate_audit_rows(test_tenant):
    ...
```

## CI evidence (pending)
- PR: <pending>
- PR head SHA: <pending>
- CI run: <pending>
- CI log excerpts: <pending>
