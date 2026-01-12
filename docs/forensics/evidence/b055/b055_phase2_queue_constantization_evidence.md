# B0.5.5 Phase 2 Queue Constantization Evidence

## Repo Pin (Pre-change baseline)
```
git rev-parse HEAD
006693770260f531fe9301883b87783afb14fe4d

git branch --show-current
b055-phase2-queue-constantization

git status --porcelain
# clean before edits
```

## Hypothesis Adjudication

### H1 — “No constantization” is purely structural
Verdict: TRUE (pre-change). No queue constants existed and `celery_app.py` hardcoded `llm`.

Evidence (pre-change):
```
rg -n "QUEUE_LLM|QUEUE_" backend/app
# no matches

rg -n "Queue\('llm'|\{'queue': 'llm'" backend/app/celery_app.py
177:            Queue('llm', routing_key='llm.#'),
184:            'app.tasks.llm.*': {'queue': 'llm', 'routing_key': 'llm.task'},
```

### H2 — Tests lock in literal strings
Verdict: TRUE (pre-change). Tests asserted literal `"llm"` queue names.

Evidence (pre-change):
```
rg -n -F "'llm'" backend/tests
backend/tests\test_b052_queue_topology_and_dlq.py:45:        assert "llm" in queue_names
backend/tests\test_b052_queue_topology_and_dlq.py:64:        assert routes["app.tasks.llm.*"]["queue"] == "llm"
backend/tests\test_b051_celery_foundation.py:191:        "housekeeping,maintenance,llm,attribution",
```

### H3 — Behavioral routing proof requires router invocation
Verdict: TRUE. Implemented routing resolution via Celery router.

Evidence (post-change):
```
rg -n "router\.route" backend/tests/test_b052_queue_topology_and_dlq.py
69:        route = celery_app.amqp.router.route({}, "app.tasks.llm.explanation", args=(), kwargs={})
```

### H4 — Import-root ambiguity risk
Verdict: PARTIAL. Repository uses `app.*` in runtime/tests, but at least one test still imports `backend.app.*`.

Evidence:
```
rg -n "from backend\.app|import backend\.app" backend/app backend/tests
backend/tests\test_channel_audit_e2e.py:17:from backend.app.core.channel_service import (
```

## Implementation Evidence (Post-change)

### EG2-A — No Hardcoded Queue Gate
Command:
```
rg -n "Queue\('llm'|\{'queue': 'llm'" backend/app/celery_app.py
```
Output:
```
# no matches
```

### EG2-B — Constant Authority Gate
Commands:
```
rg -n -F "QUEUE_LLM = " backend/app/core/queues.py
rg -n "from app\.core\.queues import QUEUE_LLM" backend/app/celery_app.py
```
Output:
```
3:QUEUE_LLM = "llm"
20:from app.core.queues import QUEUE_LLM
```

### EG2-C — Behavioral Routing Gate
Command:
```
pytest -q backend/tests/test_b052_queue_topology_and_dlq.py -q -k "QueueTopology"
```
Output:
```
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_explicit_queues_defined PASSED [ 20%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_routing_rules_defined PASSED [ 40%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_llm_task_routes_via_router PASSED [ 60%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_task_names_stable PASSED [ 80%]
backend/tests/test_b052_queue_topology_and_dlq.py::TestQueueTopology::test_queue_routing_deterministic PASSED [100%]

======================= 5 passed, 6 deselected in 0.24s =======================
```

### EG2-D — Regression Gate (Local viability)
Local full-file runs fail due to missing DB credentials/services (unchanged from baseline). CI coverage remains in `celery-foundation` job.

Pre-change local output (excerpt):
```
pytest -q backend/tests/test_b052_queue_topology_and_dlq.py -q
... InvalidPasswordError: password authentication failed for user 'app_user'

pytest -q backend/tests/test_b051_celery_foundation.py -q
... connection refused ... localhost:5432
```

### EG2-E — CI Enforcement Gate
CI job updated to run Phase 1 + Phase 2 tests in `test-backend` job.

Update (post-change):
```
.github/workflows/ci.yml
- pytest tests/test_llm_payload_contract.py -q
- pytest tests/test_b052_queue_topology_and_dlq.py -q -k "QueueTopology"
```

## Diff Summary (post-change)
```
git diff --name-status origin/main...HEAD
M	.github/workflows/ci.yml
M	backend/app/celery_app.py
A	backend/app/core/queues.py
M	backend/tests/test_b051_celery_foundation.py
M	backend/tests/test_b052_queue_topology_and_dlq.py
A	docs/forensics/evidence/b055/b055_phase2_queue_constantization_evidence.md
```

## Chain of Custody
```
git rev-parse HEAD
8343f58fd4f38d8e349b9944cd181f842803ee18

git log --oneline --decorate -n 6
8343f58 (HEAD -> b055-phase2-queue-constantization) B055 Phase2: add queue constantization evidence
d464730 B055 Phase2: introduce QUEUE_LLM constant + routing proof
0066937 (origin/main, origin/HEAD, main) Merge pull request #15 from Muk223/docs-evidence-hygiene
756e141 (origin/docs-evidence-hygiene, docs-evidence-hygiene-fix) CI: bump upload-artifact to v4
4697637 Hygiene: refresh chain-of-custody outputs
fa5d30c Hygiene: finalize evidence pack outputs

git status --porcelain
# clean
```

## PR / CI
- PR: (pending)
- CI run: (pending)
