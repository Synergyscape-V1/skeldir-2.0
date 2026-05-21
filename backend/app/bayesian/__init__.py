"""Internal B2.4 Bayesian authority package.

P2 adds deterministic source snapshot authority only. It intentionally does not
expose a FastAPI router, public API surface, LLM integration, queue planner, or
statistical runtime fitting.
"""

from app.bayesian.models import BayesianArtifact, BayesianModelFit

__all__ = ["BayesianArtifact", "BayesianModelFit"]
