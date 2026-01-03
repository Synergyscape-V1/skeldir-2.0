# B0543 Remediation Evidence Pack

## Candidate + Evidence SHAs

- Candidate SHA (C_final): edd965bb9c3801da44f7f53fd31551c80626a848
- Evidence Closure SHA (E_final): 1b350f571bd6ae5f118e14232ace34abced21085
- R7 Run (for C_final): https://github.com/Muk223/skeldir-2.0/actions/runs/20682092998 (in progress)

## SHA Topology Proof (git show --name-only)

```
commit edd965bb9c3801da44f7f53fd31551c80626a848
Author: SKELDIR Development Team <dev@skeldir.com>
Date:   Sat Jan 3 12:58:53 2026 -0600

    B0.2: add auth responses to Stripe webhooks

api-contracts/dist/openapi/v1/webhooks.stripe.bundled.yaml
api-contracts/openapi/v1/webhooks/stripe.yaml
```

```
commit 1b350f571bd6ae5f118e14232ace34abced21085
Author: SKELDIR Development Team <dev@skeldir.com>
Date:   Sat Jan 3 13:37:25 2026 -0600

    B0543: evidence closure for edd965b

docs/backend/B0543_TASK_LAYER_SUMMARY.md
```

## CI Failure Map (root-cause provenance)

| Check name | SHA | Status | Run URL | First failing line | Category | Hypothesis | Remediation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase Gates (B0.2) | (pre-fix) | FAIL | https://github.com/Muk223/skeldir-2.0/actions/runs/20681436810 | `B0.2 gate failed: Command python -m pytest tests/contract/test_mock_integrity.py -q failed` | Regression | Missing 401 responses in Stripe webhook contract | Added 401/400/500 responses to Stripe webhook endpoints + rebundled contract |

Evidence snippet (mock integrity log):

```
Contract integrity validation failed for webhooks.stripe:
  3 operation(s) failed:
    - POST /api/webhooks/stripe/charge/succeeded: Unexpected status code 401. Allowed: ['200']
    - POST /api/webhooks/stripe/payment_intent/succeeded: Unexpected status code 401. Allowed: ['200']
    - POST /api/webhooks/stripe/charge/refunded: Unexpected status code 401. Allowed: ['200']
```

## Green CI Run (C_final)

- CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/20681544928
- Conclusion: SUCCESS
- Head SHA: edd965bb9c3801da44f7f53fd31551c80626a848

## Local Reproduction Commands

- Not run locally; CI logs were used for source-of-truth failure analysis.

## Diff Summary (fix to restore green CI)

- `api-contracts/openapi/v1/webhooks/stripe.yaml`: add 400/401/500 responses to Stripe webhook endpoints returning 401 in mocks.
- `api-contracts/dist/openapi/v1/webhooks.stripe.bundled.yaml`: regenerated bundle.

## Evidence Closure Binding (docs-only)

- `docs/backend/B0543_TASK_LAYER_SUMMARY.md` updated in E_final to bind C_final and CI run URLs.
