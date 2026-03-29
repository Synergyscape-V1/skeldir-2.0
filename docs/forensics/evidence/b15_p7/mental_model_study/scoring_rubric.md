# Scoring Rubric (Async Review Mental Model)

Score each participant as `pass` only if all criteria below are met:

1. States that the system is asynchronous (not an immediate autonomous answer engine).
2. Correctly identifies that `ready_for_review` requires a human decision.
3. States that deterministic outputs are authoritative and synthesis text is explanatory.
4. States that the human reviewer owns final approval/rejection/refine decisions.

If any criterion fails, mark participant as `fail`.

## Aggregation
- `participants_completed`: count of participants with complete sessions.
- `understood_async_review_count`: count of `pass` participants.
- `comprehension_rate`: `understood_async_review_count / participants_completed`.

Gate target is met only when:
- `participants_completed >= 10`
- `comprehension_rate >= 0.80`

