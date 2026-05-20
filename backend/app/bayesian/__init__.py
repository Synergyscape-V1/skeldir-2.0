"""Internal B2.4 Bayesian authority package.

P1 exposes persistence authority only. It intentionally does not expose a
FastAPI router, public API surface, LLM integration, or statistical runtime fitting.
"""

from app.bayesian.models import BayesianArtifact, BayesianModelFit

__all__ = ["BayesianArtifact", "BayesianModelFit"]
