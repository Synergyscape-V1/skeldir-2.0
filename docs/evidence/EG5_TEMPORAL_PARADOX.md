## EG-5 Temporal Paradox (Why Human-Edited Proof Packs Rot)

### The paradox (H-EG5-IMPOSSIBLE-01)

EG-5 requires: **Proof Pack = Run = SHA**.

If you try to satisfy EG-5 by committing a proof pack file that contains:
- the candidate `GITHUB_SHA`
- the `GITHUB_RUN_ID` / run URL
- artifact IDs produced by that run

…you hit a temporal impossibility:

- At commit time, the run **has not happened yet**, so the artifact IDs and run ID do not exist.
- After the run happens, the proof pack would need to be edited to include the run/artifact IDs, which creates a **new commit** and therefore a **different SHA**.

So a repo-committed proof pack that embeds run/artifact IDs is always either:
- **one run behind**, or
- **a different SHA than the candidate**, or
- **manually edited (non-enforceable)**

This refutes the claim that a committed proof pack can be temporally coherent on the same SHA.

### The resolution (H-EG5-AUTHORITY-02)

The authoritative proof pack must be generated **inside CI during the run** and uploaded as a CI artifact.

This makes EG-5 satisfiable because:
- the proof pack is produced *after* artifact/job IDs exist
- the proof pack is bound to `GITHUB_SHA` and `GITHUB_RUN_ID` from that same run
- the proof pack can be validated as a binary CI gate

### Optional archives (honest, but not the candidate)

If you want a repo history of proof packs, archive them in a **separate bot commit** (triggered only after success) under:
`docs/evidence/proof_packs/<candidate_sha>.{json,md}`

That archive commit must be explicitly labeled as an archive of `<candidate_sha>`, not presented as the candidate itself.


