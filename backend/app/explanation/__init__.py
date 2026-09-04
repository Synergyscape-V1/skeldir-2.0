"""B2.5-P14 / B2.7 downstream explanation safety.

The package boundary is deliberate: nothing here writes to a Trust relation,
issues an envelope, or reaches a platform surface. B2.7 reads a signed
TrustEnvelope, projects it under a P14 profile, and adjudicates what may be
said about it. That is the whole of its authority.
"""
