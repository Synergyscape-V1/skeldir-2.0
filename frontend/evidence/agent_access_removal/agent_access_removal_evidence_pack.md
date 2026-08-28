# Remove Agent Access Interface — Evidence Pack

**Final Verdict: COMPLETE**

**Authority:** Approved implementation plan `remove_agent_access_f383a972`  
**Governance:** Design Implementation Agent + CRHAID six pillars (explicit supersession of `/agents` UI Spec entries)  
**Evidence pack path:** `skeldir-ui/evidence/agent_access_removal/`  
**Date:** 2026-07-16

---

## Phase 0 boundary (held)

| Bound | Resolution |
|-------|------------|
| Remove standalone Agent Access interface only | Deleted page/table/modal/fields/scope selector/secret panel + `useAgentAccess` |
| Preserve future-safe contracts | Kept `ALLOWED_AGENT_SCOPES`, `RESERVED_AGENT_SCOPES`, `agent_api_access`, client create/revoke methods, permissions, validation + secret placeholder copy |
| Onboarding Step 6 | Team invitation only; no `/app/agents` link or agent card |
| Historical evidence | Live specimens/capture index rows removed; historical PNG/report files left as records |

### Negative scope (held)

- No redesign of Team or Policy surfaces beyond copy that referenced agents
- No removal of agent scope/policy security contracts
- No stub “coming soon” agent enrollment UI
- No edits to the plan file itself

---

## Exit gates

| Gate | Method | Actual output | Result |
|------|--------|---------------|--------|
| G-01 No Agent Access UI/hook | Filesystem probe: `Agent*` under `components/governance`; `useAgentAccess.ts` | `hook=False`; no Agent* component folders | **PASS** |
| G-02 No `/app/agents` or `/agents` route/alias | Grep `ShellRoutes`/`App`/`GovernanceAliases` for `path="agents"`, `/app/agents`, `AgentsAlias`, `AgentAccessRoute` | 0 matches | **PASS** |
| G-03 No `agent-access` nav/title | Grep `navigation.ts`, `types.ts`, `navIconMap.ts`, `AuthenticatedAppShell.tsx` | 0 matches; `user-access.svg` deleted | **PASS** |
| G-04 Onboarding team-only | Grep `AddHumansOrAgentsStep.tsx` for `/app/agents`, agent path markers; L6 harness Step 6 | No agent link; team link `href="/app/settings/team"` | **PASS** |
| G-05 Reserved-scope + policy contracts intact | Source presence + L4 harness | `ALLOWED_AGENT_SCOPES` / `RESERVED_AGENT_SCOPES` / `agent_api_access` / `canCreateAgentKey` present; reserved scopes non-issuable; viewer fail-closed | **PASS** |
| G-06 Team/Policy remain functional | L4 harness + `assertLevel4RoutesExist` | Team + Policy render; `{ ok: true, missing: [] }` | **PASS** |
| G-07 Build / focused harnesses / scans | See harness section | Focused L4/L6 + redirect + L4/L1 scope PASS; meta-negative assert PASS | **PASS** (scoped; see known unrelated failures) |

### Meta-negative control

| Probe | Method | Actual | Result |
|-------|--------|--------|--------|
| `assertLevel4AgentAccessAbsent()` | Production route/nav/alias sources | `{ "ok": true, "present": [] }` | **PASS** |
| Sabotage sample with `path="agents"` + `agent-access` | `runLevel4SabotageProbes` | `agents-route-absent` + `agent-access-nav-absent` both `pass: true` | **PASS** |

---

## Harness evidence (method + output)

```text
npx vitest run src/test/level4.harness.test.tsx src/test/level6.harness.test.tsx \
  -t "Agent Access|team settings|agents alias|reserved agent|sabotage probes detect|Step 6|agent key|billing_only|Level 4 scope and secret|Level 4 routes|policy settings|viewer cannot manage|unknown role fails|PolicyAuthority|governance client|Level 6 scope|Level 6 components|redirect guard allows Level 4"
→ Test Files  2 passed
→ Tests  20 passed | 35 skipped

npx vitest run src/test/redirectGuard.test.ts
→ 15 passed

npm run audit:level4:scope
→ Level 4 scope scan: 38 files, 0 violations. Secret scan: 834 files, 0 violations.

npm run audit:level1:scope
→ filesScanned: 36, violations: [], routes.ok: true

npx tsx evidence/agent_access_removal/run_asserts.mjs
→ assertLevel4AgentAccessAbsent {"ok":true,"present":[]}
→ assertLevel4RoutesExist {"ok":true,"missing":[]}
→ sabotage agents-route-absent / agent-access-nav-absent pass:true
```

### Redirect negative control

```text
resolveSafeRedirect('/agents', { hasSession: true, hasTenant: true }, '/app')
→ { ok: false, reason: 'unknown' }
```

### Known unrelated failures (not in Agent Access removal scope)

| Check | Observation |
|-------|-------------|
| Full `npm run build` (`tsc -b`) | Pre-existing errors elsewhere (`AuditEvent.eventId`, ClaimComparisonCard bigint, etc.). **Zero** governance/`AgentAccess`/copy validation errors after restoring client contract copy keys. |
| L4/L6 “Levels 0–N regressions” token audit | Pre-existing raw hex/px violations in unrelated CSS (audit/budget/command-center/trust). Agent Access–specific tests still PASS when filtered. |

---

## Files changed (summary)

### Deleted
- `src/components/governance/AgentAccessPage/`
- `src/components/governance/AgentAccessTable/`
- `src/components/governance/AgentKeyCreationModal/`
- `src/components/governance/AgentKeyFields/`
- `src/components/governance/AgentScopeSelector/`
- `src/components/governance/AgentSecretShowOncePanel/`
- `src/governance/useAgentAccess.ts`
- `src/assets/icons/nav/user-access.svg`

### Routing / shell
- `GovernanceRoutes.tsx`, `ShellRoutes.tsx`, `App.tsx`, `GovernanceAliases.tsx`
- `redirectGuard.ts`, `shell/types.ts`, `shell/navigation.ts`, `navIconMap.ts`, `AuthenticatedAppShell.tsx`

### Onboarding
- `AddHumansOrAgentsStep.tsx`, `firstTrustEnvelope/copy.ts`, `activation/copy.ts`

### Contracts retained (pruned UI-only page copy only)
- `governance/types.ts`, `permissions.ts`, `governanceClient.ts`
- `governance/copy.ts` — kept `agent_api_access`, `agentSecretPlaceholder`, `validation.*`, policy auto-execute labels

### Enforcement
- `Level4GovernanceSpecimens.tsx`, `capture-level4-visual-evidence.ts`
- `evidence/Level_4/visual/visual-artifact-index.json` (agent specimen rows removed)
- `level4NegativeScopeScan.ts`, `level1NegativeScopeScan.ts`
- `level4.harness.test.tsx`, `level5.harness.test.tsx`, `level6.harness.test.tsx`

---

## Disposition

| State | Behavior |
|-------|----------|
| Direct `/app/agents` navigation | No Agent Access page mount; not-found / unknown-route path |
| Old `/agents` redirect target | Rejected as `unknown` by `resolveSafeRedirect` |
| Sidebar | No `agent-access` item |
| Onboarding Step 6 | Team invite path only |
| Future agent enrollment | Unimplemented; contracts preserved for later CRHAID |
