# b060_phase0_remediation_evidence_v3

```text
$ git rev-parse HEAD
6645c8dc366bc469e9806f53109e9f1f0de0fa8a
```

```text
$ git status -sb
## main...origin/main
 M docs/forensics/b060_phase0_remediation_evidence_v3.md
```

```text
$ rg -n -C 8 required: api-contracts/openapi/v1/revenue.yaml
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
72-        - data_as_of
73-      properties:
74-        tenant_id:
```

```text
$ rg -n -C 3 data_as_of api-contracts/openapi/v1/revenue.yaml
50-                currency: USD
51-                revenue_total: 125430.50
52-                verified: false
53:                data_as_of: '2026-01-26T12:00:00Z'
54-                sources: []
55-        '401':
56-          $ref: './_common/base.yaml#/components/responses/UnauthorizedError'
--
69-        - currency
70-        - revenue_total
71-        - verified
72:        - data_as_of
73-      properties:
74-        tenant_id:
75-          type: string
--
97-          type: boolean
98-          description: Whether revenue is verified through payment reconciliation
99-          example: false
100:        data_as_of:
101-          type: string
102-          format: date-time
103-          description: Timestamp of last successful upstream fetch
```

```text
$ gh run view 21381394689

? main CI · 21381394689
Triggered via push about 5 minutes ago

JOBS
? Checkout Code in 7s (ID 61548816738)
? B0.5.7 P6 E2E (Least-Privilege) in 1m22s (ID 61548826259)
? Validate Contracts in 1m50s (ID 61548826267)
? Celery Foundation B0.5.1 in 1m44s (ID 61548826277)
? Backend Integration (B0567) in 1m31s (ID 61548826278)
? Validate Phase Manifest in 12s (ID 61548826282)
? Governance Guardrails in 23s (ID 61548826296)
? B0.5.3.3 Revenue Contract Tests in 1m24s (ID 61548826308)
? Validate Migrations in 9s (ID 61548826309)
? Frontend E2E (Playwright) in 33s (ID 61548826313)
? Zero-Drift v3.2 CI Truth Layer in 1m32s (ID 61548826352)
- Test Frontend in 0s (ID 61548826379)
- Generate Pydantic Models in 0s (ID 61548826458)
- Test Backend in 0s (ID 61548826563)
? Phase Chain (B0.4 target) in 2m58s (ID 61548841018)
? Phase Gates (VALUE_03) in 2m4s (ID 61548841036)
? Phase Gates (B0.2) in 2m51s (ID 61548841037)
? Phase Gates (SCHEMA_GUARD) in 2m19s (ID 61548841038)
? Phase Gates (VALUE_05) in 2m12s (ID 61548841040)
? Phase Gates (B0.1) in 2m53s (ID 61548841041)
? Phase Gates (VALUE_04) in 2m14s (ID 61548841045)
? Phase Gates (VALUE_02) in 2m3s (ID 61548841046)
? Phase Gates (B0.4) in 2m18s (ID 61548841048)
? Phase Gates (B0.3) in 1m59s (ID 61548841049)
? Phase Gates (VALUE_01) in 2m3s (ID 61548841051)
? Proof Pack (EG-5) in 16s (ID 61549050471)

ANNOTATIONS
! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Validate Contracts: .github#18

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Chain (B0.4 target): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_03): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (B0.2): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (SCHEMA_GUARD): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_05): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (B0.1): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_04): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_02): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (B0.4): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (B0.3): .github#28

! Restore cache failed: Dependencies file is not found in /home/runner/work/skeldir-2.0/skeldir-2.0. Supported file pattern: go.sum
Phase Gates (VALUE_01): .github#28


ARTIFACTS
b057-p6-full-chain-artifacts
b0562-health-probe-logs-6645c8dc366bc469e9806f53109e9f1f0de0fa8a
b055-evidence-bundle-6645c8dc366bc469e9806f53109e9f1f0de0fa8a
phase-B0.3-evidence
phase-VALUE_03-evidence
phase-VALUE_05-evidence
phase-VALUE_04-evidence
phase-VALUE_02-evidence
phase-SCHEMA_GUARD-evidence
phase-VALUE_01-evidence
phase-B0.4-evidence
phase-B0.1-evidence
phase-chain-evidence
phase-B0.2-evidence
value-trace-proof-pack

For more information about a job, try: gh run view --job=<job-id>
View this run on GitHub: https://github.com/Muk223/skeldir-2.0/actions/runs/21381394689
```

```text
$ gh run view --job 61548826308 --log | rg -n -C 3 test_b06_realtime_revenue_v1.py
1421-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0449234Z [36;1m[0m
1422-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0449447Z [36;1mexport DATABASE_URL="$DATABASE_URL_ASYNC"[0m
1423-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0449840Z [36;1mpytest tests/test_b0533_revenue_input_contract.py -v --tb=short[0m
1424:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0450326Z [36;1mpytest tests/test_b06_realtime_revenue_v1.py -v --tb=short[0m
1425-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0450777Z [36;1mpytest ../tests/contract/test_contract_semantics.py -v --tb=short[0m
1426-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0451126Z [36;1m[0m
1427-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0451519Z [36;1mecho "? R5-5 MET / G5 PASSED: Contract tests executed (see pytest output above for pass/fail status)"[0m
--
1514-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:45.4927227Z asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
1515-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:45.9092312Z collecting ... collected 2 items
1516-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:45.9092592Z 
1517:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.0979886Z tests/test_b06_realtime_revenue_v1.py::test_realtime_revenue_v1_response_shape 
1518-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.0980613Z -------------------------------- live log call ---------------------------------
1519-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.0981366Z INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/v1/revenue/realtime "HTTP/1.1 200 OK"
1520-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.0993430Z PASSED                                                                   [ 50%]
1521:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.1014727Z tests/test_b06_realtime_revenue_v1.py::test_realtime_revenue_v1_requires_authorization 
1522-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.1015320Z -------------------------------- live log call ---------------------------------
1523-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.1015938Z INFO     httpx:_client.py:1740 HTTP Request: GET http://test/api/v1/revenue/realtime "HTTP/1.1 401 Unauthorized"
1524-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.3207080Z PASSED                                                                   [100%]
```

```text
$ gh run view --job 61548826308 --log | rg -n -C 3 test_contract_semantics.py
1422-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0449447Z [36;1mexport DATABASE_URL="$DATABASE_URL_ASYNC"[0m
1423-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0449840Z [36;1mpytest tests/test_b0533_revenue_input_contract.py -v --tb=short[0m
1424-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0450326Z [36;1mpytest tests/test_b06_realtime_revenue_v1.py -v --tb=short[0m
1425:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0450777Z [36;1mpytest ../tests/contract/test_contract_semantics.py -v --tb=short[0m
1426-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0451126Z [36;1m[0m
1427-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0451519Z [36;1mecho "? R5-5 MET / G5 PASSED: Contract tests executed (see pytest output above for pass/fail status)"[0m
1428-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:41.0484683Z shell: /usr/bin/bash -e {0}
--
1539-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:46.9766844Z asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
1540-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:47.8047631Z collecting ... collected 16 items
1541-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:47.8047957Z 
1542:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:48.3009250Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[reconciliation.bundled.yaml] SKIPPED [  6%]
1543:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:48.3061191Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[webhooks.stripe.bundled.yaml] SKIPPED [ 12%]
1544:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:48.3116099Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[webhooks.woocommerce.bundled.yaml] SKIPPED [ 18%]
1545:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:48.3170699Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[attribution.bundled.yaml] SKIPPED [ 25%]
1546:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:48.3216145Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[webhooks.paypal.bundled.yaml] SKIPPED [ 31%]
1547:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:48.3255890Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[llm-investigations.bundled.yaml] SKIPPED [ 37%]
1548:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:48.3288087Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[revenue.bundled.yaml] SKIPPED [ 43%]
1549:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.0541748Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[auth.bundled.yaml] 
1550-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.0542497Z -------------------------------- live log call ---------------------------------
1551-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.0543070Z INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/api/auth/login "HTTP/1.1 200 OK"
1552-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.0862206Z PASSED                                                                   [ 50%]
1553:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1092509Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[health.bundled.yaml] 
1554-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1093269Z -------------------------------- live log call ---------------------------------
1555-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1093825Z INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/api/health "HTTP/1.1 404 Not Found"
1556-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1172450Z INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/api/health/ready "HTTP/1.1 404 Not Found"
1557-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1241758Z INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/api/health/live "HTTP/1.1 404 Not Found"
1558-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1259121Z SKIPPED (All operations returned 404 (not implemented) in health.bun...) [ 56%]
1559:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1301848Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[llm-budget.bundled.yaml] SKIPPED [ 62%]
1560:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1354529Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[webhooks.shopify.bundled.yaml] SKIPPED [ 68%]
1561:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1401856Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[export.bundled.yaml] SKIPPED [ 75%]
1562:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1438021Z ../tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[llm-explanations.bundled.yaml] SKIPPED [ 81%]
1563:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1468919Z ../tests/contract/test_contract_semantics.py::test_auth_login_happy_path 
1564-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1469673Z -------------------------------- live log call ---------------------------------
1565-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1470227Z INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/api/auth/login "HTTP/1.1 200 OK"
1566-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1475854Z PASSED                                                                   [ 87%]
1567:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1508702Z ../tests/contract/test_contract_semantics.py::test_attribution_revenue_realtime_happy_path 
1568-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1509474Z -------------------------------- live log call ---------------------------------
1569-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1510301Z INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/api/attribution/revenue/realtime "HTTP/1.1 200 OK"
1570-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1515516Z PASSED                                                                   [ 93%]
1571:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1573448Z ../tests/contract/test_contract_semantics.py::test_coverage_report PASSED [100%]
1572-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1574017Z 
1573-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1574249Z =============================== warnings summary ===============================
1574-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1574779Z <string>:1: 136 warnings
1575-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1576633Z   <string>:1: PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated and will be removed. Use `json_schema_extra` instead. (Extra keys: 'example'). Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
1576-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1578304Z 
1577:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1578608Z tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[auth.bundled.yaml]
1578:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1580387Z   /home/runner/work/skeldir-2.0/skeldir-2.0/tests/contract/test_contract_semantics.py:96: NonInteractiveExampleWarning: The `.example()` method is good for exploring strategies, but should only be used interactively.  We recommend using `@given` for tests - it performs better, saves and replays failures to avoid flakiness, and reports minimal examples. (strategy: openapi_cases(operation=APIOperation(path='/api/auth/login',
1579-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1582170Z    method='post',
1580-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1582358Z    definition=,
1581-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1582520Z    schema=,
--
1716-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1632960Z    body=)))
1717-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1633147Z     case = operation.as_strategy().example()
1718-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1633330Z 
1719:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1633614Z tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[health.bundled.yaml]
1720:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1635330Z   /home/runner/work/skeldir-2.0/skeldir-2.0/tests/contract/test_contract_semantics.py:96: NonInteractiveExampleWarning: The `.example()` method is good for exploring strategies, but should only be used interactively.  We recommend using `@given` for tests - it performs better, saves and replays failures to avoid flakiness, and reports minimal examples. (strategy: openapi_cases(operation=APIOperation(path='/api/health',
1721-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1636830Z    method='get',
1722-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1636996Z    definition=,
1723-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1637158Z    schema=,
--
1819-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1671219Z    body=)))
1820-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1671398Z     case = operation.as_strategy().example()
1821-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1671744Z 
1822:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1672035Z tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[health.bundled.yaml]
1823:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1673784Z   /home/runner/work/skeldir-2.0/skeldir-2.0/tests/contract/test_contract_semantics.py:96: NonInteractiveExampleWarning: The `.example()` method is good for exploring strategies, but should only be used interactively.  We recommend using `@given` for tests - it performs better, saves and replays failures to avoid flakiness, and reports minimal examples. (strategy: openapi_cases(operation=APIOperation(path='/api/health/ready',
1824-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1675424Z    method='get',
1825-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1675590Z    definition=,
1826-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1675754Z    schema=,
--
1894-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.1702130Z    body=)))
1895-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.3955607Z     case = operation.as_strategy().example()
1896-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.3956148Z 
1897:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.3956945Z tests/contract/test_contract_semantics.py::test_contract_semantic_conformance[health.bundled.yaml]
1898:B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.3960557Z   /home/runner/work/skeldir-2.0/skeldir-2.0/tests/contract/test_contract_semantics.py:96: NonInteractiveExampleWarning: The `.example()` method is good for exploring strategies, but should only be used interactively.  We recommend using `@given` for tests - it performs better, saves and replays failures to avoid flakiness, and reports minimal examples. (strategy: openapi_cases(operation=APIOperation(path='/api/health/live',
1899-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.3964223Z    method='get',
1900-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.3964622Z    definition=,
1901-B0.5.3.3 Revenue Contract Tests	R5-5 / Gate G5 - Run B0.5.3.3 contract tests (2 tests must pass)	2026-01-27T01:51:50.3964996Z    schema=,
```

