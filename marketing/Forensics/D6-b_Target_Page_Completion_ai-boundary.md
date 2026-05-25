# D6-b Target Page Completion — /ai-boundary

## 1. Source Copy Used

- `c:\Users\ayewhy\Downloads\YMYL Content\skeldir-ai_boundary -v1.md` (implemented with D6-b public-safety reframing in `marketing/src/app/ai-boundary/page.tsx`)

## 2. Files Changed

| File | Change | Reason |
|---|---|---|
| `src/app/ai-boundary/page.tsx` | Rewritten | v1 concepts, BLUF + Key facts, IP-safe framing, proof-link graph, `#llm-does-not-calculate` and `#agent-policy` anchors preserved |
| `scripts/discoverability/lib/d6-ai-boundary-exposure.mjs` | **New** | D6-b forbidden leakage + truth/agent boundaries + structure |
| `scripts/discoverability/lib/d5-trust-proof.mjs` | Updated | Public boundary satisfies D5 review-status without snake_case badge |
| `scripts/discoverability-d6-harness.mjs` | Updated | Gate **6i** |
| `scripts/discoverability-d6-negative-controls.mjs` | Updated | NC-D6-22/23 |

## 3. Public-Safety Changes

| Source concept | Final public framing | Mechanism removed? |
|---|---|---|
| semantic truth hash | Each explanation tied to the verified record it describes | **yes** |
| explanation cache keys | Avoids treating repeated explanations as new financial evidence | **yes** |
| template versions | (removed) | **yes** |
| signing key rotation | (removed) | **yes** |
| deterministic lookup | When verified evidence cannot be found, answer must say so | **yes** |
| TrustEnvelope contract | TrustEnvelopes provide evidence and policy context | **yes** |
| read-only boundary | LLM explanations not allowed to change authoritative financial values | **yes** |
| Design Partner Mode | Some downstream actions may require approval or policy limits | **yes** |
| action authority states | Authorization boundaries / approval without enum names | **yes** |
| externalization stages | (removed) | **yes** |

## 4. Static HTML Proof

From `marketing/out/ai-boundary.html`:

```html
<h1>AI Boundary</h1>
<h2>Bottom Line Up Front</h2>
<h2>Key facts</h2>
<h2>What LLMs do in Skeldir</h2>
<h2>Why LLMs do not compute financial truth</h2>
<h2>Deterministic grounding</h2>
<h2>Bounded explanations</h2>
<h2>Policy for AI agents consuming Skeldir</h2>
<h2>Scope and trust boundary</h2>
<p>does not calculate … authoritative … advisory … deterministic … TrustEnvelope</p>
<p>Last updated: February 2026</p>
```

## 5. IP Exposure Scan

```bash
grep -Ei "semantic truth hash|cache key|Design Partner Mode|read-only boundary|simulation_only" out/ai-boundary.html
# → no matches (PASS)
```

## 6. Placeholder Theater Scan

```bash
grep -Ei "technical_disclosure_only|Owner_Skeldir|placeholder|coming soon" out/ai-boundary.html
# → no matches (PASS)
```

## 7. Agent-Boundary Proof

- Deterministic value = authoritative (BLUF + sections)
- Verification status = authoritative (BLUF + grounding)
- LLM explanation = advisory (BLUF + agent policy)
- Agent action constrained by policy/approval (agent policy section)
- No `simulation_only`, `approval_required`, `auto-executable`, or phase-gate language in HTML

## 8. Proof-Link Graph

- `/methodology` ✓
- `/trust-envelope` ✓
- `/revenue-verification` ✓
- `/attribution-methodology` ✓
- `/discrepancy-taxonomy` ✓
- `/api` ✓
- `/docs` ✓

## 9. Discoverability Regression

| Harness | Result |
|---|---|
| `npm run build` | **PASS** |
| `npm run discoverability:d5` (skip-build) | **PASS** — 71/0; `#llm-does-not-calculate`, `#agent-policy` |
| `npm run discoverability:d6` (skip-build) | **PASS** — 122/0; gate **6i** |
| `npm run discoverability:d6:negative-controls` | **PASS** — 25/0 |

## 10. Verdict

**PASS**
