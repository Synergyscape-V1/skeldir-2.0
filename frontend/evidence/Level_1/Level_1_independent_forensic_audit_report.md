# Independent Audit Report — Level 1 Product Entry and Tenant Existence

**Audit type:** Adversarial forensic audit — Level 1 (local validation standard)  
**Repository:** `c:\Users\ayewhy\Frontend_4\skeldir-ui`  
**Audit date:** 2026-06-27  
**Auditor posture:** Evidence pack and remediation claims treated as unverified hypotheses  

---

## 1. Final Verdict

**ACCEPT**

---

## 2. Verdict Rationale

Level 1 implements product-owned `/login` and `/signup` as state-graph entry points — not marketing pages — with typed auth client isolation, session bootstrap, tenant creation handoff, fail-closed redirect guarding, business-email policy, provider-specific OAuth buttons, and controlled post-auth routes (`/entry/session-ready`, `/entry/workspace-created`). No Level 2+ application shell, Command Center, onboarding, or downstream product surfaces are registered or rendered.

Independently reproduced:

- `npm run build` → exit 0  
- `npm run audit:level0` → exit 0 (36/36 Level 0 tests; substrate scans clean)  
- `npm run audit:level1:scope` → exit 0  
- Level 1 Vitest harness → **31/31 tests** pass  
- **60 PNG** visual artifacts on disk with indexed specimen matrix  
- Sabotage: `fetch(` in `LoginForm.tsx` → level1 scope scan exit 1  

Login establishes session state before navigation; signup establishes tenant state via `establishTenant` before handoff; unsafe redirects (`https://`, `javascript:`, `/app`, `/onboarding`, `/unknown`) are rejected at render and in tests. Auth transport `fetch` is confined to `authClient.ts`; form components contain no direct network calls.

Non-blocking gaps remain in auth-outcome UI test exhaustiveness and a latent `mapAuthOutcomeToDetail` detail-pass-through path that is not exercised by current forms. Neither blocks Level 1 closure under the local validation standard.

```
PHASE STATUS:  COMPLETE (local validation standard)
ADVANCEMENT:   PERMITTED to Level 2 substrate-dependent work
```

---

## 3. Local Environment

| Field | Value |
|-------|-------|
| Repo path | `c:\Users\ayewhy\Frontend_4\skeldir-ui` |
| Node | v22.22.0 |
| npm | 11.6.2 |
| OS | Windows 10.0.26200 |
| Router | `react-router-dom` v7.18.0 (`BrowserRouter` in `src/app/App.tsx`) |

### Commands executed

| Command | Exit | Result |
|---------|------|--------|
| `npm run build` | 0 | Library + app build succeeds |
| `npm run audit:level0` | 0 | tokens 58/0, scope 26/0, financial 31/0, L0 tests 36/36 |
| `npm run audit:level1:scope` | 0 | 18 files, 0 violations, routes ok |
| `npx vitest run src/test/level1.harness.test.tsx src/test/redirectGuard.test.ts --coverage` | 0 | 31/31 pass; L1 coverage 70.45% stmts |
| Sabotage `fetch(` in LoginForm | 1 | `fetch-in-form-component` violation detected |

---

## 4. Gate Results

| Gate | Result | Evidence | Failure reason |
|------|--------|----------|----------------|
| 01 — Product-Owned Entry Routes | **PASS** | `App.tsx` registers `/login`, `/signup`; `LoginPage`/`SignupPage` render forms on `PageSurface`+`Card`; no app shell | — |
| 02 — Session and Tenant State Correctness | **PASS** | `establishSession`/`establishTenant`; handoff pages guard on session/tenant; double-submit test; invalid credentials / tenant exists tests | — |
| 03 — Safe Redirect and Scope Boundary | **PASS** | `redirectGuard.ts` + 11 redirect tests; unsafe redirect UI test; level1 scope scan clean; sabotage passes | — |
| 04 — Form and OAuth Robustness | **PASS** | BusinessEmailInput policy tests; OAuth accessible names; consumer email rejection; pending/disabled via submitLock | — |
| 05 — Level 0 Substrate Reuse | **PASS** | L0 audit green; token audit includes auth surfaces 58/0; Card/PageSurface/Typography/ErrorBanner used | — |
| 06 — Non-Vacuous Runtime Proof | **PASS** | 31 tests execute; fetch-in-form sabotage fails scope scan | — |
| 07 — Visual and Accessibility Evidence | **PASS** | 60 PNGs; 15 specimens × 4 viewports; interaction tests in L1 harness (not axe-only) | — |
| 08 — Auth Copy and Secret-Safety | **PASS** | `mapAuthOutcomeToMessage` sanitizes `unknown_error`; secret grep clean; no tokens in copy/tests | — |
| 09 — Auth Client Boundary Integrity | **PASS** | `fetch` only in `authClient.ts`; `AuthOutcome` union typed; forms inject `AuthClient` in tests | — |
| 10 — Evidence Pack Integrity | **PASS** | Claims independently reproduced: 31 tests, 60 PNGs, build/audit exit codes match | — |

**Gate tally:** 10 PASS · 0 FAIL

---

## 5. Hypothesis Results

| Hypothesis | Result | Evidence | Risk |
|------------|--------|----------|------|
| H-AUDIT-L1-01 Product entry routes | **Confirmed** | Routes in `App.tsx`; `LoginPage` test; visual `login-default` specimens | Missing product auth entry |
| H-AUDIT-L1-02 No Level 2+ build | **Confirmed** | `level1NegativeScopeScan` 0 violations; no `/app` route registration | Premature downstream surfaces |
| H-AUDIT-L1-03 Level 0 regression | **Confirmed** | `audit:level0` exit 0; 36/36 L0 tests | Substrate regression |
| H-AUDIT-L1-04 Auth client boundary | **Confirmed** | No `fetch` in forms; `authClient.ts` isolated | Scattered transport logic |
| H-AUDIT-L1-05 AuthOutcome union total | **Confirmed** | All 14 outcome kinds in `types.ts`; `outcomeMapping.ts` covers each | Unmapped auth states |
| H-AUDIT-L1-06 Session bootstrap deterministic | **Confirmed** | `SessionBootstrapBoundary` skeleton→validate→ready; `SessionReadyPage` redirects if no session | Session-unknown routing |
| H-AUDIT-L1-07 Tenant creation handoff | **Confirmed** | `establishTenant` on success; `WorkspaceCreatedPage` requires tenant; signup cannot redirect to `/app` | Tenant-less downstream access |
| H-AUDIT-L1-08 BusinessEmailInput | **Confirmed** | Consumer domain rejected; `aria-invalid`; `role=alert`; normalize unit test | Consumer email acceptance |
| H-AUDIT-L1-09 OAuth buttons | **Confirmed** | `Continue with {GitHub|Google|Microsoft}` aria-labels; pending/disabled props; visual `oauth-button-states` | Generic/inaccessible OAuth |
| H-AUDIT-L1-10 Redirect guard fail-closed | **Confirmed** | external/javascript/unknown/app/onboarding blocked in tests | Open redirect / premature `/app` |
| H-AUDIT-L1-11 Auth copy safe | **Confirmed** | Unknown error detail not rendered; message sanitization test | Raw backend leakage |
| H-AUDIT-L1-12 Double submit prevented | **Confirmed** | `submitLock` + test: `login` called once on double click | Duplicate auth calls |
| H-AUDIT-L1-13 Level 0 reuse | **Confirmed** | L0 primitives in auth pages; token audit clean on auth CSS | Parallel ad hoc UI system |
| H-AUDIT-L1-14 Visual evidence | **Confirmed** | 60 PNGs; index at `evidence/Level_1/visual/visual-artifact-index.json` | Unreviewable auth UI |
| H-AUDIT-L1-15 Interaction accessibility | **Confirmed** | Tab, aria-invalid, double-submit, OAuth aria-label tests; not axe-only | Keyboard/SR exclusion |
| H-AUDIT-L1-16 Harness non-vacuous | **Confirmed** | fetch-in-form sabotage fails scope scan | Decorative green harness |

---

## 6. Route Inventory

### Registered routes (`src/app/App.tsx`)

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | Redirect → `/login` | Entry default |
| `/login` | `LoginPage` | Product login |
| `/signup` | `SignupPage` | Product signup |
| `/entry/session-ready` | `SessionReadyPage` | Controlled post-login handoff |
| `/entry/workspace-created` | `WorkspaceCreatedPage` | Controlled post-signup handoff |
| `/dev/specimens` | Level 0 gallery | Dev evidence |
| `/dev/auth-specimens` | Level 1 auth gallery | Dev evidence |
| `*` | Redirect → `/login` | Fail-closed unknown routes |

### Forbidden routes found in implementation

**None registered.** `LEVEL2_PLUS_BLOCKED_ROUTES` appear only in `redirectGuard.ts` (blocklist definition — permitted).

### Runtime route evidence

- `LoginPage` renders `Typography` h1 + `LoginForm` inside `Card`/`PageSurface` — no sidebar, health strip, or Command Center  
- Handoff pages explicitly state app shell not yet available (`AUTH_COPY.handoffSessionBody`)  
- Visual specimens cover all required auth states at mobile/tablet/desktop/wide  

---

## 7. Auth State Evidence

### AuthOutcome union (`src/auth/types.ts`)

All directive-required states present:

`success_session_established` · `success_tenant_created` · `invalid_credentials` · `email_not_business` · `tenant_already_exists` · `oauth_provider_unavailable` · `oauth_callback_error` · `rate_limited` · `network_error` · `session_expired` · `permission_denied` · `tenant_creation_pending` · `tenant_creation_failed` · `unknown_error`

### Login state matrix

| State | UI behavior | Test evidence |
|-------|-------------|---------------|
| success_session_established | `establishSession` + safe redirect | Harness positive login |
| invalid_credentials | `AuthErrorBanner` safe copy | Harness negative |
| unsafe redirect | `UnsafeRedirectBanner` | Harness + visual specimen |
| already_authenticated | Info banner | Session bootstrap test |
| session_expired | Banner via `?reason=session_expired` | Page param + visual specimen |
| oauth pending | Disabled buttons + loading label | Visual `login-oauth-pending` |
| double submit | `submitLock` blocks second call | Harness negative |

*Not individually UI-render tested but mapped:* `network_error`, `rate_limited`, `oauth_callback_error`, `oauth_provider_unavailable`, `permission_denied`, `unknown_error` — all route through `mapAuthOutcomeToMessage` to canonical copy.

### Signup/tenant state matrix

| State | UI behavior | Test evidence |
|-------|-------------|---------------|
| success_tenant_created | `establishTenant` + handoff navigation | Harness positive |
| email_not_business | Field error + policy copy | Harness negative |
| tenant_already_exists | `AuthErrorBanner` | Harness negative |
| tenant_creation_pending | Banner copy (code path) | Visual specimen; no dedicated harness render test |
| tenant_creation_failed | Safe banner | Visual specimen |
| OAuth session-without-tenant | `tenantCreationFailed` message | Code path in `runOAuth` |

### OAuth state matrix

| Provider | Accessible name | Pending/disabled |
|----------|-----------------|------------------|
| GitHub | `Continue with GitHub` | Shared `OAuthButtonBase` |
| Google | `Continue with Google` | Structurally identical |
| Microsoft | `Continue with Microsoft` | Structurally identical |

---

## 8. Redirect Guard Evidence

### Unsafe redirect cases (all rejected — `ok: false`)

| Target | Reason |
|--------|--------|
| `https://evil.test` | external |
| `//external.example` | external (code: `^//` check) |
| `javascript:alert(1)` | javascript |
| `/unknown` | unknown |
| `/app` | level2_blocked |
| `/onboarding` | onboarding_premature |

### Safe fallback behavior

| Context | Fallback |
|---------|----------|
| Post-login (empty redirect) | `/entry/session-ready` |
| Post-signup (empty redirect) | `/entry/workspace-created` |
| Permitted handoff | `/entry/workspace-created` with session+tenant |

`PostAuthRedirectGuard` and `TenantCreationBoundary` exist and are exported; redirect resolution is primarily enforced in `LoginForm`/`SignUpForm` via `resolveSafeRedirect` — equivalent responsibility, not duplicated unsafe paths.

---

## 9. Form and Accessibility Evidence

### BusinessEmailInput

- Accepts `ops@acme.com`; rejects `user@gmail.com`  
- Normalizes `Ops@Acme.COM` + whitespace (unit test)  
- `aria-invalid="true"` + `role="alert"` on validation failure  
- Visual specimen: `business-email-input-states`

### LoginForm

- Uses `FormField` with label association  
- `aria-live="polite"` status region for announcements  
- Submit via Enter (native form submit)  
- No `fetch` in component source

### SignUpForm

- `BusinessEmailInput` + workspace/password fields  
- Tenant outcomes mapped to safe copy  
- Double-submit lock shared pattern with login

### OAuth buttons

- Provider-specific `aria-label`  
- Disabled while `oauthPending !== null` or `submitting`  
- Keyboard-activatable via `SubmitButton` (button elements)

### Keyboard/focus/live-region findings

| Check | Status |
|-------|--------|
| Tab reachability | BusinessEmailInput tab test |
| Field error association | `aria-describedby` on `FormField` |
| Live-region announcements | `aria-live` div in forms |
| OAuth accessible names | GitHub harness test; Google/Microsoft structurally identical |
| Focus after failed submit | Not explicitly tested — non-blocking gap |

---

## 10. Negative Scope Evidence

| Scan | Result |
|------|--------|
| App shell leakage | None — `PageSurface` only, no `ResponsiveShell` sidebar on auth pages |
| Downstream route leakage | `level1NegativeScopeScan` 0 violations |
| Backend/API in forms | None; sabotage `fetch` in LoginForm detected |
| Export/integration leakage | None in auth scan dirs |

Level 0 negative scope scan excludes `src/app` and `src/components/auth` intentionally so L0 substrate audit remains green after L1 — documented in `negativeScopeScan.ts`.

---

## 11. Harness Non-Vacuousness Evidence

| Sabotage introduced | Expected failure | Actual | Valid? |
|---------------------|------------------|--------|--------|
| `fetch(` in `LoginForm.tsx` | Level1 scope exit 1 | Exit 1, `fetch-in-form-component` | **Yes** |
| External redirect `https://evil.test` | `resolveSafeRedirect` false | Test passes | **Yes** |
| Raw backend in `unknown_error` message | Sanitized message | Message ≠ SQL detail | **Yes** |
| `/app` redirect | Blocked | Test passes | **Yes** |

---

## 12. Visual Evidence

| Field | Value |
|-------|-------|
| Artifact count | **60** PNG files |
| Index path | `evidence/Level_1/visual/visual-artifact-index.json` |
| Generated at | `2026-06-27T16:39:03.283Z` |
| Viewports | mobile, tablet, desktop, wide |
| Specimens (15) | login-default, login-session-expired, login-invalid-credentials, login-network-failure, login-oauth-pending, login-oauth-error, login-unsafe-redirect-blocked, signup-default, signup-invalid-business-email, signup-tenant-already-exists, signup-tenant-creation-pending, signup-tenant-creation-failed, signup-post-signup-handoff, oauth-button-states, business-email-input-states |
| Missing states/viewports | **None identified** |

---

## 13. Critical Findings

*No blocker findings.*

### Non-critical findings

**F-L1-01 — Auth outcome UI test matrix incomplete (Medium)**  
- Not all `AuthOutcome` kinds have dedicated render tests (e.g. `network_error`, `rate_limited`, `tenant_creation_pending` UI paths).  
- Mapping exists in `outcomeMapping.ts`; risk is regression without detection.

**F-L1-02 — `mapAuthOutcomeToDetail` latent detail pass-through (Low)**  
- `outcomeMapping.ts` returns `outcome.detail` for `unknown_error`, `tenant_creation_failed`, `email_not_business`.  
- Current forms do not pass backend `detail` to `AuthErrorBanner`; no observed leakage.  
- Recommend hardening to never surface raw `detail`.

**F-L1-03 — `PostAuthRedirectGuard` not mounted on App routes (Low)**  
- Guard logic duplicated in forms and handoff `Navigate` checks.  
- Functionally equivalent today; consolidation would reduce drift risk.

**F-L1-04 — Protocol-relative redirect `//host` not explicitly tested (Low)**  
- `isExternalUrl` rejects `^//`; add explicit test for parity with directive Eval 05.

---

## 14. Completion Determination

**Level 1 is empirically complete** under the **local validation standard**.

Product-owned `/login` and `/signup` establish the authenticated product state graph entry points with deterministic session and tenant handoffs, fail-closed redirect guarding, typed auth client isolation, business-email enforcement, accessible OAuth entry, Level 0 substrate reuse, non-vacuous harness proof, and 60 indexed visual artifacts — without implementing Level 2+ downstream surfaces.

---

## 15. Required Remediation Before Acceptance

*Not applicable — verdict is ACCEPT.*

### Recommended forward obligations (non-blocking)

1. Add render tests for remaining `AuthOutcome` UI paths.  
2. Harden `mapAuthOutcomeToDetail` to never return raw backend `detail`.  
3. Add explicit `//external` redirect guard test.  
4. Mount `PostAuthRedirectGuard` on handoff routes to centralize redirect policy.  

---

*End of Level 1 independent forensic audit report.*
