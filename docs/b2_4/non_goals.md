# B2.4 Non-Goals

M5 is design-only. B2.4 implementation remains blocked until M5, M6, and M7 authorize entry.

Explicitly forbidden during M5:

- Model fitting.
- PyMC installation.
- PyMC-Marketing installation.
- ArviZ installation.
- MCMC execution.
- Convergence implementation.
- New migrations.
- `bayesian_model_fits` or `bayesian_artifacts` table creation.
- Public API endpoints.
- Trust API implementation.
- LLM explanation behavior changes.
- B2.3 redesign.
- Attribution semantics changes.
- Webhook verifier changes.
- RLS policy changes.
- Frontend/dashboard work.
- MCP tools.
- Policy automation.
- Production Bayesian activation.
- Dependency cloning, vendoring, or forks.

Permitted during M5:

- Design documents under `docs/b2_4/`.
- Internal confidence metadata schema under `contracts/internal/`.
- Static validator under `scripts/ci/`.
- CI registry/subsumption registration for the M5 static validator.
- Makefile target for static validation.
- Completion/evidence records.
