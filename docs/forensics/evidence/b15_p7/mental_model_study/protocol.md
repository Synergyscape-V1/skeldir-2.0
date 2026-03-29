# Mental-Model Validation Protocol (B1.5-P7)

Human Execution Required

No fabricated participant outcomes

## Objective
Validate whether users understand that B1.5 surfaces are asynchronous recommendation workflows
that require human review, not synchronous autonomous chat decisions.

## Participants
- Target: 10 participants.
- Profile: product operators/reviewers who would use budget or investigation recommendations.
- Exclusion: engineers who implemented the B1.5 feature in this phase.

## Study Tasks
1. Launch an investigation request from the bounded B1.5 surface.
2. Observe progress and status updates.
3. Identify when review is required.
4. Execute a review action (approve/reject/refine).
5. Explain in their own words what the system is doing and who owns the final decision.

## Primary Success Metric
- `understood_async_review_count / participants_completed >= 0.80`
- With `participants_completed >= 10`.

## Required Evidence Artifacts
- Completed `participant_results_template.csv` (or equivalent with same columns).
- Session notes or recordings referenced by participant ID.
- Updated `status.json` with real completion counts and measured comprehension rate.

