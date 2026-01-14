B0.5.5 Phase 4 CI Artifact Context Gathering Evidence
=====================================================

Timestamp: 2026-01-14T09:51:24.5389054-06:00
Branch: b055-phase3-v4-orm-coc-idempotency
Local HEAD: d1b778853611875b3dd20fd0ddd6a2432d65d321
PR: not yet opened (local branch only)

Chain-of-custody
----------------

Commands:

```
git rev-parse HEAD
git status --porcelain
```

Outputs:

```
d1b778853611875b3dd20fd0ddd6a2432d65d321
```

```
<clean>
```

CI workflow inventory (repo truth)
----------------------------------

Workflow files:

```
Get-ChildItem .github/workflows | Select-Object -ExpandProperty Name
```

```
.gitkeep
b0541-view-registry.yml
b0542-refresh-executor.yml
b0543-matview-task-layer.yml
b0545-convergence.yml
channel_governance_ci.yml
ci.yml
contract-artifacts.yml
contract-enforcement.yml
contract-publish.yml
contract-validation.yml
contracts.yml
empirical-validation.yml
mock-contract-validation.yml
phase-gates.yml
r0-preflight-validation.yml
r1-contract-runtime.yml
r1-validation.yml
r2-data-truth-hardening.yml
r3-ingestion-under-fire.yml
r4-worker-failure-semantics.yml
r5-context-gathering.yml
r5-remediation.yml
r6-worker-resource-governance.yml
r7-final-winning-state.yml
schema-deploy-production.yml
schema-drift-check.yml
schema-validation.yml
workflow-yaml-lint.yml
```

PR-triggered workflows:

```
rg -n "pull_request" .github/workflows
```

```
.github/workflows\schema-validation.yml:4:  pull_request:
.github/workflows\empirical-validation.yml:6:  pull_request:
.github/workflows\b0545-convergence.yml:4:  pull_request:
.github/workflows\ci.yml:6:  pull_request:
.github/workflows\ci.yml:340:    if: github.event_name == 'pull_request' || contains(github.event.head_commit.modified, 'backend/') || contains(github.event.head_commit.added, 'backend/')
.github/workflows\ci.yml:956:          if [[ "${{ github.event_name }}" != "pull_request" ]]; then
.github/workflows\b0543-matview-task-layer.yml:6:  pull_request:
.github/workflows\contract-validation.yml:13:  pull_request:
.github/workflows\contract-validation.yml:98:    if: github.event_name == 'pull_request'
.github/workflows\b0542-refresh-executor.yml:6:  pull_request:
.github/workflows\contract-artifacts.yml:19:  pull_request:
.github/workflows\r5-remediation.yml:18:  pull_request:
.github/workflows\channel_governance_ci.yml:22:  pull_request:
.github/workflows\b0541-view-registry.yml:6:  pull_request:
.github/workflows\contracts.yml:9:  pull_request:
```

Artifact capability audit
-------------------------

Upload/download usage in workflows:

```
rg -n "upload-artifact|download-artifact|retention-days|actions/upload-artifact" .github/workflows
```

```
.github/workflows\b0545-convergence.yml:254:        uses: actions/upload-artifact@v4
.github/workflows\b0545-convergence.yml:258:          retention-days: 30
.github/workflows\ci.yml:220:        uses: actions/upload-artifact@v4
.github/workflows\ci.yml:226:          retention-days: 7
.github/workflows\ci.yml:295:        uses: actions/upload-artifact@v4
.github/workflows\ci.yml:301:          retention-days: 7
.github/workflows\ci.yml:328:        uses: actions/upload-artifact@v4
.github/workflows\ci.yml:334:          retention-days: 30
.github/workflows\ci.yml:499:        uses: actions/upload-artifact@v4
.github/workflows\ci.yml:503:          retention-days: 90
.github/workflows\contract-enforcement.yml:24:        uses: actions/download-artifact@v4
.github/workflows\contract-enforcement.yml:49:        uses: actions/upload-artifact@v4
.github/workflows\contract-enforcement.yml:53:          retention-days: 1
.github/workflows\contract-enforcement.yml:71:        uses: actions/download-artifact@v4
.github/workflows\contract-enforcement.yml:90:        uses: actions/upload-artifact@v4
.github/workflows\contract-enforcement.yml:94:          retention-days: 1
.github/workflows\contract-enforcement.yml:112:        uses: actions/download-artifact@v4
.github/workflows\contract-enforcement.yml:118:        uses: actions/download-artifact@v4
.github/workflows\contract-enforcement.yml:142:        uses: actions/upload-artifact@v4
.github/workflows\contract-enforcement.yml:148:          retention-days: 7
.github/workflows\contract-enforcement.yml:166:        uses: actions/download-artifact@v4
.github/workflows\contract-enforcement.yml:172:        uses: actions/download-artifact@v4
.github/workflows\contract-enforcement.yml:194:        uses: actions/upload-artifact@v4
.github/workflows\contract-enforcement.yml:198:          retention-days: 7
.github/workflows\contract-artifacts.yml:54:        uses: actions/upload-artifact@v4
.github/workflows\contract-artifacts.yml:58:          retention-days: 7
.github/workflows\contract-artifacts.yml:81:        uses: actions/download-artifact@v4
.github/workflows\contract-artifacts.yml:128:        uses: actions/download-artifact@v4
.github/workflows\contract-artifacts.yml:170:        uses: actions/download-artifact@v4
.github/workflows\contract-artifacts.yml:188:        uses: actions/upload-artifact@v4
.github/workflows\contract-artifacts.yml:192:          retention-days: 30
.github/workflows\contracts.yml:77:        uses: actions/upload-artifact@v4
.github/workflows\contracts.yml:81:          retention-days: 30
.github/workflows\empirical-validation.yml:67:        uses: actions/upload-artifact@v4
.github/workflows\empirical-validation.yml:71:          retention-days: 90
.github/workflows\empirical-validation.yml:116:        uses: actions/download-artifact@v4
.github/workflows\empirical-validation.yml:216:        uses: actions/upload-artifact@v4
.github/workflows\empirical-validation.yml:220:          retention-days: 90
.github/workflows\empirical-validation.yml:245:        uses: actions/download-artifact@v4
.github/workflows\empirical-validation.yml:344:        uses: actions/upload-artifact@v4
.github/workflows\empirical-validation.yml:348:          retention-days: 90
.github/workflows\empirical-validation.yml:368:        uses: actions/download-artifact@v4
.github/workflows\empirical-validation.yml:437:        uses: actions/upload-artifact@v4
.github/workflows\empirical-validation.yml:441:          retention-days: 90
.github/workflows\empirical-validation.yml:476:        uses: actions/download-artifact@v4
.github/workflows\empirical-validation.yml:569:        uses: actions/upload-artifact@v4
.github/workflows\empirical-validation.yml:573:          retention-days: 90
.github/workflows\empirical-validation.yml:588:        uses: actions/download-artifact@v4
.github/workflows\empirical-validation.yml:634:        uses: actions/upload-artifact@v4
.github/workflows\empirical-validation.yml:638:          retention-days: 90
.github/workflows\empirical-validation.yml:656:        uses: actions/download-artifact@v4
.github/workflows\phase-gates.yml:59:        uses: actions/upload-artifact@v4
.github/workflows\phase-gates.yml:63:          retention-days: 7
.github/workflows\phase-gates.yml:113:        uses: actions/upload-artifact@v4
.github/workflows\phase-gates.yml:117:          retention-days: 7
.github/workflows\phase-gates.yml:174:        uses: actions/upload-artifact@v4
.github/workflows\phase-gates.yml:178:          retention-days: 7
.github/workflows\phase-gates.yml:198:        uses: actions/upload-artifact@v4
.github/workflows\phase-gates.yml:202:          retention-days: 7
.github/workflows\mock-contract-validation.yml:129:        uses: actions/upload-artifact@v4
.github/workflows\mock-contract-validation.yml:133:          retention-days: 30
.github/workflows\r1-contract-runtime.yml:762:        uses: actions/upload-artifact@5d5d22a31266ced268874388b861e4b58bb5c2f3  # v4.3.1 pinned by SHA
.github/workflows\r1-contract-runtime.yml:766:          retention-days: 90
.github/workflows\r2-data-truth-hardening.yml:641:        uses: actions/upload-artifact@v4
.github/workflows\r2-data-truth-hardening.yml:645:          retention-days: 90
.github/workflows\r3-ingestion-under-fire.yml:134:        uses: actions/upload-artifact@v4
.github/workflows\r4-worker-failure-semantics.yml:167:        uses: actions/upload-artifact@v4
.github/workflows\r0-preflight-validation.yml:468:        uses: actions/upload-artifact@5d5d22a31266ced268874388b861e4b58bb5c2f3  # v4.3.1 pinned by SHA
.github/workflows\r0-preflight-validation.yml:473:          retention-days: 90
.github/workflows\r1-validation.yml:79:        uses: actions/upload-artifact@v4
.github/workflows\r1-validation.yml:212:        uses: actions/upload-artifact@v4
.github/workflows\r1-validation.yml:333:        uses: actions/upload-artifact@v4
.github/workflows\r1-validation.yml:489:        uses: actions/upload-artifact@v4
.github/workflows\r1-validation.yml:558:        uses: actions/upload-artifact@v4
.github/workflows\r1-validation.yml:728:        uses: actions/upload-artifact@v4
.github/workflows\r1-validation.yml:743:        uses: actions/download-artifact@v4
.github/workflows\r1-validation.yml:911:        uses: actions/upload-artifact@v4
.github/workflows\r5-context-gathering.yml:116:        uses: actions/upload-artifact@v4
.github/workflows\r5-remediation.yml:171:        uses: actions/upload-artifact@v4
.github/workflows\schema-deploy-production.yml:120:        uses: actions/upload-artifact@v4
.github/workflows\schema-deploy-production.yml:124:          retention-days: 90
.github/workflows\r6-worker-resource-governance.yml:310:        uses: actions/upload-artifact@v4
.github/workflows\schema-validation.yml:72:        uses: actions/upload-artifact@v4
.github/workflows\schema-validation.yml:76:          retention-days: 7
```

DB provisioning truth (alembic vs ORM)
--------------------------------------

No ORM create_all/drop_all in backend (no matches):

```
rg -n "create_all|drop_all|metadata\\.create_all|Base\\.metadata" backend
```

```
<no matches>
```

Conftest DB guard + engine usage (no alembic in tests):

```
rg -n "DATABASE_URL|engine|session|alembic|create_all|Base" backend/tests/conftest.py
```

```
16:# In CI, DATABASE_URL MUST be provided by step env vars - no fallbacks, no defaults.
18:    if "DATABASE_URL" not in os.environ:
20:            "[B0.5.3.3 Gate C] CI FAILURE: DATABASE_URL not set in environment. "
34:    dsn = os.environ["DATABASE_URL"]
59:from app.db.session import engine
109:    async with engine.begin() as conn:
117:    async with engine.begin() as conn:
152:    async with engine.begin() as conn:
162:    async with engine.begin() as conn:
```

Backend repository contains only documentation references to Alembic, not test harness calls:

```
rg -n "alembic upgrade|alembic current|alembic heads|command\\.upgrade" backend
```

```
backend\README.md:36:alembic upgrade head
backend\README.md:81:alembic upgrade head
backend\validation\evidence\database\migration_cycle_log.txt:4:-- alembic upgrade heads -- 
backend\validation\evidence\database\migration_cycle_log.txt:84:-- alembic upgrade heads (final) -- 
```

CI (ci.yml) runs Alembic before tests in at least one job:

```
rg -n "services:|postgres|DATABASE_URL|alembic|pytest" .github/workflows/ci.yml
```

```
133:    services:
134:      postgres:
135:        image: postgres:15-alpine
152:      DATABASE_URL: postgresql://app_user:app_user@127.0.0.1:5432/skeldir_phase
342:      DATABASE_URL: postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation
361:            pytest tests/test_llm_payload_contract.py -q
365:          pytest tests/test_b052_queue_topology_and_dlq.py -q -k "QueueTopology"
371:    services:
372:      postgres:
373:        image: postgres:15-alpine
386:      DATABASE_URL: postgresql://app_user:app_user@127.0.0.1:5432/skeldir_validation
434:          alembic upgrade 202511131121
435:          alembic upgrade skeldir_foundation@head
437:          alembic upgrade head
490:            pytest \
```

Hook/injection points for evidence generation
---------------------------------------------

Session-scope fixtures available:

```
rg -n "scope=.*session" backend/tests
```

```
backend/tests\test_b0536_attribution_e2e.py:49:@pytest.fixture(scope="session")
backend/tests\test_b045_webhooks.py:30:@pytest_asyncio.fixture(scope="session")
backend/tests\test_b046_integration.py:40:@pytest_asyncio.fixture(scope="session")
backend/tests\test_b051_celery_foundation.py:170:@pytest.fixture(scope="session")
```

No pytest_sessionstart/pytest_sessionfinish hooks found:

```
rg -n "pytest_sessionstart|pytest_sessionfinish" backend/tests
```

```
<no matches>
```

Schema snapshot feasibility (pg_dump + existing evidence)
---------------------------------------------------------

Workflow uses pg_dump schema-only:

```
rg -n "pg_dump|schema-only|schema" .github/workflows/r1-contract-runtime.yml
```

```
207:          podman exec skeldir-r1-postgres pg_dump --schema-only --no-owner --no-privileges -U $POSTGRES_USER $POSTGRES_DB > "$ARTIFACTS_DIR/DB_SCHEMA/schema_after_run1.sql"
220:          podman exec skeldir-r1-postgres pg_dump --schema-only --no-owner --no-privileges -U $POSTGRES_USER $POSTGRES_DB > "$ARTIFACTS_DIR/DB_SCHEMA/schema_after_run2.sql"
```

Repo already contains pg_dump output snapshots:

```
Get-Content backend/validation/evidence/database/current_schema_20251127_111144.sql -TotalCount 5
```

```
--
-- PostgreSQL database dump
--
```

Evidence/manifests/checksum tooling exists (selected excerpts from repo search):

```
rg -n "manifest|sha256|checksum" -S .github/workflows backend/validation docs/forensics scripts
```

```
scripts\generate-checksums.js:10: * Output: checksums.json with SHA256 hashes for all contract files
.github/workflows\b0545-convergence.yml:205:          ls -l "${EVIDENCE_DIR}" > "${EVIDENCE_DIR}/evidence_manifest.txt"
.github/workflows\empirical-validation.yml:578:  phase-5-manifest:
.github/workflows\empirical-validation.yml:595:          cat > evidence_registry/EMPIRICAL_CHAIN.md << 'MANIFEST'
docs/forensics\artifacts_vt_run3\phase-VALUE_04\MANIFEST.md:1:# Evidence Registry Manifest
```

Candidate evidence bundle inventory (current tooling reality)
------------------------------------------------------------

Feasible bundle components based on repo + workflows:

- Alembic status: `alembic current`, `alembic heads`, `alembic history` (CI already runs upgrade steps; outputs can be captured).
- Postgres schema snapshot: `pg_dump --schema-only` (already used in `r1-contract-runtime.yml`).
- DB catalog checks: `pg_catalog` / `information_schema` queries (seen in Phase 3 tests; no explicit script yet).
- Test logs: pytest output already captured in CI steps (can redirect to files).
- Migration logs: evidence of `alembic upgrade head` is present in CI (`ci.yml` lines 434-437).
- Environment snapshots: `python --version`, `pip freeze`, git SHA.
- Manifest/checksum: scripts exist (`scripts/generate-checksums.js`, `scripts/phase_gates/validate_manifest.py`, `r5` scripts compute sha256).

Gaps summary mapped to Phase 4 exit gates
-----------------------------------------

EG-CG1 (CI artifact capability reality): Artifacts are uploaded across multiple workflows, but no single standardized "evidence bundle" across PR gating jobs. Evidence shows fragmented artifact uploads.
EG-CG2 (DB provisioning truth): CI runs alembic in `ci.yml`, but tests do not invoke alembic in fixtures. Evidence needed to ensure all Phase 4 evidence jobs use migrations.
EG-CG3 (Hook/injection points): Session-scoped fixtures exist; no pytest_sessionstart/finish hooks. Potential injection points exist but no dedicated evidence fixture yet.
EG-CG4 (Bundle feasibility inventory): pg_dump usage exists in workflows, and evidence/manifest tooling exists; no unified bundle spec yet.
EG-CG5 (Chain-of-custody): This evidence file is newly created and must be committed/pushed to the active branch for PR visibility.
