"""B2.5-P14 / B2.8 downstream simulation and proposal safety.

B2.8 is request-driven in Design Partner Mode. Nothing in this package is
scheduled, and nothing in it reaches a platform-write capability: it reads a
signed TrustEnvelope, decides admission, and -- only when admission passes --
computes a deterministic integer allocation that a human may later act on.
"""
