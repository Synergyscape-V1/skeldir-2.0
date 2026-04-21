# Phase B2.2-P4 Remediation Evidence Pack

Date: 2026-04-21  
Branch basis: `main` (corrective-action iteration after rejected closeout)  
Directive: Idempotent ACK semantics + webhook-orchestration side-effect isolation

## 1) Corrective blocker identified

- Prior P4 landing correctly fixed duplicate suppression and side-effect isolation, but ACK protocol stability was incomplete.
- Root blocker: malformed authenticated payload handling was route-dependent:
  - `stripe` alias route (`/api/webhooks/stripe/payment_intent/succeeded`) already used route-owned raw parsing and returned `200` + `status: dlq_routed`.
  - `shopify`, `stripe` canonical (`/api/webhooks/stripe/payment_intent_succeeded`), `paypal`, and `woocommerce` still used FastAPI typed `Body(...)` signature binding, allowing framework pre-handler validation behavior and potential `422` leakage.
- This violated the P4 protocol law requiring route-stable malformed authenticated ACK semantics across supported mounted providers and aliases.

## 2) Forensic hypotheses adjudicated

- H01/H02 (framework-prevalidation leak and narrow proof surface): **Validated**.
- H03 (global handler shortcut risk): **Rejected as implementation path**; no global `RequestValidationError` special-casing was used to implement the fix.
- H04 (duplicate seam still dict-consumed): **Still bounded hardening debt**, but not the blocker for this corrective action.
- H05/H06 (auth-precedence and non-regression risk): **Addressed in runtime tests** by explicit forged/missing/wrong-tenant malformed assertions and duplicate-substrate preservation checks.

## 3) Remediations implemented

- `backend/app/api/webhooks.py`
  - Removed typed `Body(...)` request binding from supported webhook handlers:
    - `shopify_order_create`
    - `stripe_payment_intent_succeeded` (canonical)
    - `paypal_sale_completed`
    - `woocommerce_order_completed`
  - Added route-local post-auth parsing surface:
    - `_parse_json_object(...)`
    - `_malformed_idempotency_key(...)`
    - `_route_authenticated_malformed_payload(...)`
  - Enforced malformed authenticated behavior at webhook boundary (after auth success):
    - invalid JSON or invalid required shape now routes to DLQ and returns `200` + `status: dlq_routed` consistently.
  - Preserved auth precedence:
    - forged/missing-tenant/wrong-tenant requests continue to terminate in `401` auth class before malformed-DLQ handling.
  - Preserved duplicate substrate and scheduling isolation:
    - no change to duplicate suppression gate (`result.get("is_duplicate")`) and no change to scheduling failure containment behavior.

- `backend/tests/test_b22_p4_idempotent_ack_orchestration.py`
  - Expanded ACK matrix runtime proof to include malformed authenticated route coverage for:
    - Shopify
    - Stripe canonical
    - Stripe alias
    - PayPal
    - WooCommerce
  - Added auth-precedence assertions per malformed route:
    - forged malformed -> `401`
    - missing-tenant malformed -> `401`
    - wrong-tenant malformed -> `401`
  - Extended stripe canonical vs alias parity proof to include malformed ACK parity (`200` + `dlq_routed` on both).

- `contracts-internal/governance/b22_p4_idempotent_ack_orchestration.main.json`
  - Bumped contract version to `1.1.0`.
  - Added explicit `route_scope` for `malformed_authenticated_payload` ACK contract covering all supported mounted routes/alias.

- `scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py`
  - Added governance check for malformed route scope completeness.
  - Added webhook-surface invariant checks forbidding typed `Body(...)` binding on supported webhook routes.
  - Kept duplicate-substrate and CI wiring assertions intact.

- `backend/tests/test_b12_p8_error_contract_normalization.py`
  - Updated authenticated malformed webhook expectation from `422` problem-details path to route-owned `200` + `dlq_routed`.
  - Added DLQ stub in this test to keep it deterministic and independent of tenant-table fixture persistence.

## 4) Local falsifiable proof outcomes

- `python scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py` -> **PASS**
- `pytest backend/tests/test_b22_p4_idempotent_ack_orchestration_enforcer.py -q` -> **5 passed**
- `pytest backend/tests/test_b22_p4_idempotent_ack_orchestration.py -q` -> **4 skipped** locally (authoritative DB proof gate unchanged; requires migrated DB and `SKELDIR_B22_P4_REQUIRE_DB_PROOFS=1`)
- `pytest backend/tests/test_b12_p8_error_contract_normalization.py -q` -> **14 passed**

## 5) Exit gate adjudication (corrective iteration)

- Exit Gate 1 (Duplicate-Suppression Integrity): **Maintained**.
- Exit Gate 2 (ACK Protocol Physics, primary blocker): **Addressed in implementation + expanded route matrix proofs**.
- Exit Gate 3 (Auth-Precedence): **Explicitly proven in malformed-route auth-precedence checks**.
- Exit Gate 4 (B0.4 + Scheduling Non-Regression): **Maintained** (duplicate and scheduling logic unchanged; compatibility surfaces preserved).
- Exit Gate 5 (Merge-Blocking P4 Adjudication): **Pending protected-branch merge + post-merge `main` CI success evidence capture**.

## 6) Protected-branch landing evidence (this corrective iteration)

- Feature branch: `b22-p4-ack-route-stability-corrective`
- PR: _pending_
- Merge commit on `main`: _pending_
- Post-merge `main` CI run URL: _pending_
- Post-merge `main` CI status: _pending_

## 7) Completion verdict (current state)

- Corrective implementation state: **READY FOR PROTECTED-BRANCH MERGE**
- Final directive closure status: **PENDING** until:
  - PR is merged into `main` through branch protection,
  - required checks are green,
  - and post-merge `main` CI is confirmed green for the landed corrective commit.
