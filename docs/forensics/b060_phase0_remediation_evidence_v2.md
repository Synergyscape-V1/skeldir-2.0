# b060_phase0_remediation_evidence_v2

```text
$ git status -sb
## main...origin/main
```

```text
$ git rev-parse HEAD
52663c6fe34fe6f860f25adc8c22257394a0d36d
```

```text
$ rg -n -C 8 "required:" api-contracts/openapi/v1/revenue.yaml
58-          $ref: './_common/base.yaml#/components/responses/RateLimitError'
59-        '500':
60-          $ref: './_common/base.yaml#/components/responses/ServerError'
61-
62-components:
63-  schemas:
64-    RealtimeRevenueV1Response:
65-      type: object
66:      required:
67-        - tenant_id
68-        - interval
69-        - currency
70-        - revenue_total
71-        - verified
72-      properties:
73-        tenant_id:
74-          type: string
```

```text
$ rg -n -C 3 "data_as_of" api-contracts/openapi/v1/revenue.yaml
50-                currency: USD
51-                revenue_total: 125430.50
52-                verified: false
53:                data_as_of: '2026-01-26T12:00:00Z'
54-                sources: []
55-        '401':
56-          $ref: './_common/base.yaml#/components/responses/UnauthorizedError'
--
96-          type: boolean
97-          description: Whether revenue is verified through payment reconciliation
98-          example: false
99:        data_as_of:
100-          type:
101-            - string
102-            - "null"
```

```text
$ rg -n -C 3 "class RealtimeRevenueV1Response|data_as_of" backend/app/schemas/revenue.py
10-from pydantic import BaseModel, Field
11-
12-
13:class RealtimeRevenueV1Response(BaseModel):
14-    tenant_id: Annotated[UUID, Field(example="00000000-0000-0000-0000-000000000000")]
15-    """
16-    Tenant identifier associated with the revenue data
--
31-    """
32-    Whether revenue is verified through payment reconciliation
33-    """
34:    data_as_of: Annotated[Optional[datetime], Field(example="2026-01-26T12:00:00Z")] = None
35-    """
36-    Timestamp of the last successful upstream data fetch (nullable during interim)
37-    """
```

```text
$ rg -n -C 5 "RealtimeRevenueV1Response|required:|data_as_of" api-contracts/dist/openapi/v1/revenue.bundled.yaml
25-      security:
26-        - bearerAuth: []
27-      parameters:
28-        - name: X-Correlation-ID
29-          in: header
30:          required: true
31-          schema: &ref_4
32-            type: string
33-            format: uuid
34-          description: Unique request correlation ID for distributed tracing
35-        - name: Authorization
36-          in: header
37:          required: true
38-          schema: &ref_5
39-            type: string
40-          description: Bearer token for authentication (format - Bearer <token>)
41-      responses:
42-        '200':
--
49-              description: Request correlation ID echoed back
50-          content:
51-            application/json:
52-              schema:
53-                type: object
54:                required: &ref_2
55-                  - tenant_id
56-                  - interval
57-                  - currency
58-                  - revenue_total
59-                  - verified
--
82-                    example: 125430.5
83-                  verified:
84-                    type: boolean
85-                    description: Whether revenue is verified through payment reconciliation
86-                    example: false
87:                  data_as_of:
88-                    type:
89-                      - string
90-                      - 'null'
91-                    format: date-time
92-                    description: Timestamp of last successful upstream fetch (nullable during interim)
--
101-                tenant_id: 00000000-0000-0000-0000-000000000000
102-                interval: minute
103-                currency: USD
104-                revenue_total: 125430.5
105-                verified: false
106:                data_as_of: '2026-01-26T12:00:00Z'
107-                sources: []
108-        '401':
109-          description: Unauthorized - invalid or missing authentication
110-          headers: &ref_6
111-            X-Correlation-ID:
--
116-          content: &ref_7
117-            application/problem+json:
118-              schema:
119-                type: object
120-                description: RFC7807 Problem Details for HTTP APIs with Skeldir extensions
121:                required: &ref_0
122-                  - type
123-                  - title
124-                  - status
125-                  - detail
126-                  - instance
--
188-          content: &ref_9
189-            application/problem+json:
190-              schema:
191-                type: object
192-                description: RFC7807 Problem Details for HTTP APIs with Skeldir extensions
193:                required: *ref_0
194-                properties: *ref_1
195-        '500':
196-          description: Internal server error
197-          headers: &ref_10
198-            X-Correlation-ID:
--
202-          content: &ref_11
203-            application/problem+json:
204-              schema:
205-                type: object
206-                description: RFC7807 Problem Details for HTTP APIs with Skeldir extensions
207:                required: *ref_0
208-                properties: *ref_1
209-components:
210-  schemas:
211:    RealtimeRevenueV1Response:
212-      type: object
213:      required: *ref_2
214-      properties: *ref_3
215-    ProblemDetails:
216-      type: object
217-      description: RFC7807 Problem Details for HTTP APIs with Skeldir extensions
218:      required: *ref_0
219-      properties: *ref_1
220-  securitySchemes:
221-    bearerAuth:
222-      type: http
223-      scheme: bearer
--
225-      description: JWT Bearer token authentication
226-  parameters:
227-    CorrelationId:
228-      name: X-Correlation-ID
229-      in: header
230:      required: true
231-      schema: *ref_4
232-      description: Unique request correlation ID for distributed tracing
233-    Authorization:
234-      name: Authorization
235-      in: header
236:      required: true
237-      schema: *ref_5
238-      description: Bearer token for authentication (format - Bearer <token>)
239-  responses:
240-    UnauthorizedError:
241-      description: Unauthorized - invalid or missing authentication
```

```text
$ "C:\Program Files\Git\bin\bash.exe" scripts/contracts/bundle.sh
[bundle] Preparing output directory: /c/Users/ayewhy/II SKELDIR II/api-contracts/dist/openapi/v1
[bundle] Bundling core contracts...
[bundle] ? auth.bundled.yaml
[bundle] ? attribution.bundled.yaml
[bundle] ? revenue.bundled.yaml
[bundle] ? reconciliation.bundled.yaml
[bundle] ? export.bundled.yaml
[bundle] ? health.bundled.yaml
[bundle] Bundling webhook contracts...
[bundle] ? webhooks.shopify.bundled.yaml
[bundle] ? webhooks.woocommerce.bundled.yaml
[bundle] ? webhooks.stripe.bundled.yaml
[bundle] ? webhooks.paypal.bundled.yaml
[bundle] Bundling LLM contracts...
[bundle] ? llm-investigations.bundled.yaml
[bundle] ? llm-budget.bundled.yaml
[bundle] ? llm-explanations.bundled.yaml
[bundle] Copying _common directory for reference...
[bundle] ? _common directory
[bundle] All 12 OpenAPI contracts bundled successfully.
[bundle] Artifacts ready under api-contracts/dist/openapi/v1/.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\auth.yaml...
[39m?? Created a bundle for [34mopenapi\v1\auth.yaml[39m at [34mdist\openapi\v1\auth.bundled.yaml[39m [32m20ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\attribution.yaml...
[39m?? Created a bundle for [34mopenapi\v1\attribution.yaml[39m at [34mdist\openapi\v1\attribution.bundled.yaml[39m [32m24ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\revenue.yaml...
[39m?? Created a bundle for [34mopenapi\v1\revenue.yaml[39m at [34mdist\openapi\v1\revenue.bundled.yaml[39m [32m19ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\reconciliation.yaml...
[39m?? Created a bundle for [34mopenapi\v1\reconciliation.yaml[39m at [34mdist\openapi\v1\reconciliation.bundled.yaml[39m [32m20ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\export.yaml...
[39m?? Created a bundle for [34mopenapi\v1\export.yaml[39m at [34mdist\openapi\v1\export.bundled.yaml[39m [32m21ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\health.yaml...
[39m?? Created a bundle for [34mopenapi\v1\health.yaml[39m at [34mdist\openapi\v1\health.bundled.yaml[39m [32m19ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\webhooks\shopify.yaml...
[39m?? Created a bundle for [34mopenapi\v1\webhooks\shopify.yaml[39m at [34mdist\openapi\v1\webhooks.shopify.bundled.yaml[39m [32m24ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\webhooks\woocommerce.yaml...
[39m?? Created a bundle for [34mopenapi\v1\webhooks\woocommerce.yaml[39m at [34mdist\openapi\v1\webhooks.woocommerce.bundled.yaml[39m [32m24ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\webhooks\stripe.yaml...
[39m?? Created a bundle for [34mopenapi\v1\webhooks\stripe.yaml[39m at [34mdist\openapi\v1\webhooks.stripe.bundled.yaml[39m [32m21ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\webhooks\paypal.yaml...
[39m?? Created a bundle for [34mopenapi\v1\webhooks\paypal.yaml[39m at [34mdist\openapi\v1\webhooks.paypal.bundled.yaml[39m [32m22ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\llm-investigations.yaml...
[39m?? Created a bundle for [34mopenapi\v1\llm-investigations.yaml[39m at [34mdist\openapi\v1\llm-investigations.bundled.yaml[39m [32m21ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\llm-budget.yaml...
[39m?? Created a bundle for [34mopenapi\v1\llm-budget.yaml[39m at [34mdist\openapi\v1\llm-budget.bundled.yaml[39m [32m22ms[39m.

    [33m+[33m-------------------------------------------------------[33m+[39m
    [33m¦                                                       ¦[39m
    [33m¦[39m  A new version of [36mRedocly CLI[39m ([32m2.14.9[39m) is available.  [33m¦[39m
    [33m¦[39m  Update now: `[36mnpm i -g @redocly/cli@latest[39m`.          [33m¦[39m
    [33m¦[39m  Changelog: https://redocly.com/docs/cli/changelog/   [33m¦[39m
    [33m¦                                                       ¦[39m
    [33m+[33m-------------------------------------------------------[33m+[39m

[90mbundling openapi\v1\llm-explanations.yaml...
[39m?? Created a bundle for [34mopenapi\v1\llm-explanations.yaml[39m at [34mdist\openapi\v1\llm-explanations.bundled.yaml[39m [32m19ms[39m.
```

```text
$ python scripts/contracts/check_dist_complete.py
Bundle completeness check:
  Expected: 13
  Present:  13
  Missing:  0

OK: All bundles present
```

```text
$ pytest -q

=================================== ERRORS ====================================
__________ ERROR collecting backend/tests/test_channel_audit_e2e.py ___________
ImportError while importing test module 'C:\Users\ayewhy\II SKELDIR II\backend\tests\test_channel_audit_e2e.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python311\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend\tests\test_channel_audit_e2e.py:17: in <module>
    from backend.app.core.channel_service import (
E   ModuleNotFoundError: No module named 'backend'
______ ERROR collecting backend/tests/test_no_raw_inserts_core_tables.py ______
ImportError while importing test module 'C:\Users\ayewhy\II SKELDIR II\backend\tests\test_no_raw_inserts_core_tables.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python311\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend\tests\test_no_raw_inserts_core_tables.py:15: in <module>
    from backend.tests.builders.manifest import CORE_TABLE_BUILDERS
E   ModuleNotFoundError: No module named 'backend'
________ ERROR collecting backend/tests/test_schema_contract_guard.py _________
ImportError while importing test module 'C:\Users\ayewhy\II SKELDIR II\backend\tests\test_schema_contract_guard.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python311\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend\tests\test_schema_contract_guard.py:20: in <module>
    from backend.tests.builders.manifest import CORE_TABLE_BUILDERS, TENANT_SCOPED_TABLES
E   ModuleNotFoundError: No module named 'backend'
_ ERROR collecting backend/tests/value_traces/test_value_01_revenue_trace.py __
ImportError while importing test module 'C:\Users\ayewhy\II SKELDIR II\backend\tests\value_traces\test_value_01_revenue_trace.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python311\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend\tests\value_traces\test_value_01_revenue_trace.py:32: in <module>
    from backend.tests.builders.core_builders import build_attribution_allocation, build_tenant
E   ModuleNotFoundError: No module named 'backend'
_ ERROR collecting backend/tests/value_traces/test_value_02_constraint_trace.py _
ImportError while importing test module 'C:\Users\ayewhy\II SKELDIR II\backend\tests\value_traces\test_value_02_constraint_trace.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python311\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend\tests\value_traces\test_value_02_constraint_trace.py:17: in <module>
    from backend.tests.builders.core_builders import build_tenant
E   ModuleNotFoundError: No module named 'backend'
_ ERROR collecting backend/tests/value_traces/test_value_03_provider_handshake.py _
ImportError while importing test module 'C:\Users\ayewhy\II SKELDIR II\backend\tests\value_traces\test_value_03_provider_handshake.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python311\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend\tests\value_traces\test_value_03_provider_handshake.py:36: in <module>
    from backend.tests.builders.core_builders import build_tenant
E   ModuleNotFoundError: No module named 'backend'
_ ERROR collecting backend/tests/value_traces/test_value_05_centaur_enforcement.py _
ImportError while importing test module 'C:\Users\ayewhy\II SKELDIR II\backend\tests\value_traces\test_value_05_centaur_enforcement.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python311\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend\tests\value_traces\test_value_05_centaur_enforcement.py:33: in <module>
    from backend.tests.builders.core_builders import build_tenant
E   ModuleNotFoundError: No module named 'backend'
============================== warnings summary ===============================
<string>:1: 136 warnings
  <string>:1: PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated and will be removed. Use `json_schema_extra` instead. (Extra keys: 'example'). Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR backend/tests/test_channel_audit_e2e.py
ERROR backend/tests/test_no_raw_inserts_core_tables.py
ERROR backend/tests/test_schema_contract_guard.py
ERROR backend/tests/value_traces/test_value_01_revenue_trace.py
ERROR backend/tests/value_traces/test_value_02_constraint_trace.py
ERROR backend/tests/value_traces/test_value_03_provider_handshake.py
ERROR backend/tests/value_traces/test_value_05_centaur_enforcement.py
!!!!!!!!!!!!!!!!!!! Interrupted: 7 errors during collection !!!!!!!!!!!!!!!!!!!
======================= 136 warnings, 7 errors in 1.59s =======================
```

```text
$ gh run view 21375931759

? main CI · 21375931759
Triggered via push about 5 minutes ago

JOBS
? Checkout Code in 8s (ID 61531947488)
? B0.5.7 P6 E2E (Least-Privilege) in 1m5s (ID 61531963979)
? B0.5.3.3 Revenue Contract Tests in 1m6s (ID 61531963983)
? Celery Foundation B0.5.1 in 1m53s (ID 61531963988)
? Backend Integration (B0567) in 1m23s (ID 61531963995)
? Governance Guardrails in 21s (ID 61531964009)
? Validate Contracts in 1m49s (ID 61531964020)
? Validate Phase Manifest in 12s (ID 61531964032)
? Zero-Drift v3.2 CI Truth Layer in 1m34s (ID 61531964048)
? Frontend E2E (Playwright) in 32s (ID 61531964052)
? Validate Migrations in 9s (ID 61531964063)
- Test Frontend in 0s (ID 61531964273)
- Generate Pydantic Models in 0s (ID 61531964470)
- Test Backend in 0s (ID 61531964491)
? Phase Chain (B0.4 target) in 3m0s (ID 61531989055)
? Phase Gates (SCHEMA_GUARD) in 2m11s (ID 61531989121)
? Phase Gates (B0.3) in 2m18s (ID 61531989136)
? Phase Gates (VALUE_01) in 2m15s (ID 61531989138)
? Phase Gates (VALUE_04) in 2m6s (ID 61531989140)
? Phase Gates (VALUE_05) in 2m18s (ID 61531989145)
? Phase Gates (B0.1) in 3m16s (ID 61531989146)
? Phase Gates (VALUE_03) in 2m10s (ID 61531989151)
? Phase Gates (B0.4) in 2m23s (ID 61531989154)
? Phase Gates (B0.2) in 2m33s (ID 61531989169)
? Phase Gates (VALUE_02) in 2m7s (ID 61531989202)
? Proof Pack (EG-5) in 11s (ID 61532326869)

ANNOTATIONS
! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Validate Contracts: .github#18

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Chain (B0.4 target): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (SCHEMA_GUARD): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (B0.3): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_01): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_04): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_05): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (B0.1): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_03): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (B0.4): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (B0.2): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_02): .github#28


ARTIFACTS
b057-p6-full-chain-artifacts
b0562-health-probe-logs-52663c6fe34fe6f860f25adc8c22257394a0d36d
b055-evidence-bundle-52663c6fe34fe6f860f25adc8c22257394a0d36d
phase-VALUE_04-evidence
phase-SCHEMA_GUARD-evidence
phase-VALUE_01-evidence
phase-VALUE_05-evidence
phase-B0.3-evidence
phase-VALUE_03-evidence
phase-VALUE_02-evidence
phase-B0.4-evidence
phase-chain-evidence
phase-B0.2-evidence
phase-B0.1-evidence
value-trace-proof-pack

For more information about a job, try: gh run view --job=<job-id>
View this run on GitHub: https://github.com/Muk223/skeldir-2.0/actions/runs/21375931759
```

```text
$ gh run view --job 61531963983 --log | rg -n -C 3 "test_realtime_revenue_v1_response_shape"
1513-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.4132023Z asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
1514-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.8284514Z collecting ... collected 2 items
1515-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.8284923Z 
1516:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9873045Z tests/test_b06_realtime_revenue_v1.py::test_realtime_revenue_v1_response_shape 
1517-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9873959Z -------------------------------- live log call ---------------------------------
1518-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9874856Z INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/v1/revenue/realtime "HTTP/1.1 200 OK"
1519-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9886299Z PASSED                                                                   [ 50%]
```

```text
$ gh run view --job 61531963983 --log | rg -n -C 3 "test_realtime_revenue_v1_requires_authorization"
1517-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9873959Z -------------------------------- live log call ---------------------------------
1518-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9874856Z INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/v1/revenue/realtime "HTTP/1.1 200 OK"
1519-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9886299Z PASSED                                                                   [ 50%]
1520:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9906755Z tests/test_b06_realtime_revenue_v1.py::test_realtime_revenue_v1_requires_authorization 
1521-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9907899Z -------------------------------- live log call ---------------------------------
1522-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:44.9908911Z INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/v1/revenue/realtime "HTTP/1.1 401 Unauthorized"
1523-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-26T22:12:45.1606235Z PASSED                                                                   [100%]
```
