# D5 Claim-Proof Registry

**Phase:** D5 — Trust Proof Boundary and Legal/Security Surface
**Last reviewed:** 2026-05-23
**Owner:** Skeldir Product Engineering

This registry is the human-readable counterpart of `discoverability.claim-proof-registry.json`. Every high-stakes Skeldir marketing claim must appear in both. The harness `scripts/discoverability-d5-harness.mjs` enforces:

- shape (required fields present, claim_category in the enum, proof_route is a D5 route),
- anchor existence (`proof_anchor` resolves to an `id="..."` in the built HTML for `proof_route`),
- absence of invented compliance / security claims in any of the registered source files.

Field meanings:

| Field | Meaning |
|---|---|
| `claim_id` | Stable identifier across reviews. |
| `claim_text` | The exact claim as it appears in public copy. |
| `source_route` | Public route where the claim appears. |
| `source_component_or_file` | Source file the claim copy originates from. |
| `claim_category` | One of: `revenue_verification`, `deterministic_truth`, `privacy_no_pii`, `ai_boundary`, `auditability`, `trust_envelope`, `attribution_methodology`, `discrepancy_handling`, `benchmark_confidence`, `security`. |
| `risk_level` | `high` for claims a buyer would treat as material; `medium` for supporting claims. |
| `proof_route` | The D5 proof route that backs the claim. |
| `proof_anchor` | `#section-id` on the proof route — must exist in built HTML. |
| `proof_type` | `methodology_disclosure`, `concept_specification`, `ai_boundary_disclosure`, `security_disclosure`, `taxonomy_disclosure`. |
| `owner` | Team responsible for keeping the proof page truthful. |
| `legal_review_required` | True for any claim that may carry legal exposure (e.g. PII). |
| `status` | `operator_approved`, `technical_disclosure_only`, `legal_review_required`, or `blocked_missing_content`. |
| `last_reviewed` | Date the claim was last re-verified against the proof page. |

## Claims

| ID | Claim (short) | Source route | Risk | Proof route → anchor | Owner | Status | Last reviewed |
|---|---|---|---|---|---|---|---|
| D5-CLAIM-001 | Every ad dollar traced, verified to the source. | `/` | high | `/methodology#deterministic-reconciliation` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-002 | Skeldir reconciles platform-reported ad revenue with verified commerce and payment evidence. | `/` | high | `/revenue-verification#reconciliation` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-003 | AI Agents and teams execute from confirmed truth. | `/` | high | `/ai-boundary#agent-policy` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-004 | Skeldir is deterministic revenue-verification infrastructure that exposes audit-ready financial truth through TrustEnvelopes. | `/` | high | `/trust-envelope#what-it-is` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-005 | Deterministic financial truth backed by a provenance chain and semantic truth hash. | `/trust-envelope` | high | `/trust-envelope#audit-trail` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-006 | LLMs explain deterministic truth but do not calculate financial truth. | `/ai-boundary` | high | `/ai-boundary#llm-does-not-calculate` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-007 | Discrepancies are classified, not averaged. | `/methodology` | medium | `/discrepancy-taxonomy#timing-mismatch` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-008 | Attribution models answer bounded questions; they do not prove causality. | `/methodology` | medium | `/attribution-methodology#bounded-questions` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-009 | Security posture under explicit status taxonomy; we do not claim certifications we have not earned. | `/security` | high | `/security#status-taxonomy` | Skeldir Security & Engineering | technical_disclosure_only | 2026-05-23 |
| D5-CLAIM-010 | Privacy-minimizing design within reconciliation engine; "no PII" not asserted globally. | `/security` | high | `/security#pii-policy` | Skeldir Security & Engineering | technical_disclosure_only | 2026-05-23 |
| D5-CLAIM-011 | Commerce evidence (Shopify) and payment evidence (Stripe) ingested independently of the ad platform. | `/revenue-verification` | medium | `/revenue-verification#commerce-evidence` | Skeldir Product Engineering | operator_approved | 2026-05-23 |
| D5-CLAIM-012 | TrustEnvelope confidence status is an enumerated verification state, not a probabilistic score. | `/trust-envelope` | medium | `/trust-envelope#confidence-status` | Skeldir Product Engineering | operator_approved | 2026-05-23 |

## Notes

- **`/privacy`** (D6-b) is a noindex **privacy posture summary**, not a registered high-stakes claim surface. Claims about security posture and PII boundaries proof to `/security` anchors.
- **Legal placeholder routes** (`/terms`, `/gdpr`) remain noindex until operator/legal supplies approved copy.
- **Status `technical_disclosure_only`** means the claim is engineering-grade posture disclosure that does not require legal sign-off (e.g. how the deterministic engine works), or that the row openly explains why the broader compliance claim is *not* made.
- **No `SOC 2 certified`, `ISO 27001 certified`, `GDPR compliant`, `HIPAA compliant`, `PCI compliant`, `fully encrypted`, or `no PII` claims appear above**, by design. The harness blocks any source file from introducing those phrases unless the registry first records an `operator_approved` row with cited audit evidence.
- **AI boundary claim** (D5-CLAIM-006) is the structurally most important high-stakes claim because Skeldir markets to buyers who explicitly worry about LLMs computing financial numbers. It is anchored at `#llm-does-not-calculate` so the proof is reachable by a single deep link.
