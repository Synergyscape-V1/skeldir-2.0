# Canonical Git Root — Skeldir Webpage (D2 governance)

## Problem

Running `git status` from `c:\Users\ayewhy\Skeldir Webpage\marketing` previously resolved `git rev-parse --show-toplevel` to `C:/Users/ayewhy` because a `.git` directory exists at the user profile root. That scope is unsafe for discoverability remediation: it treats the entire home directory as the repository.

## Resolution

A dedicated Git repository was initialized at:

`c:\Users\ayewhy\Skeldir Webpage`

using initial branch **`feat/discoverability-remediation`** (no commits to `main` / `master` inside this root).

Worktrees under `marketing/` remain the Netlify `base = "marketing"` source per deployment evidence; the **repository root** is the folder that contains `marketing/`, not `marketing/` alone.

## Remote

The production remote referenced in `discoverability.routes.json` metadata is:

`https://github.com/Muk223/skeldir-2.0.git`

This local repo may be linked with `git remote add origin <url>` when you are ready to push the feature branch. **Nothing in Phase D2 was pushed automatically.**

## Verification

From `marketing/`:

```powershell
git rev-parse --show-toplevel
git branch --show-current
```

Expected: toplevel ends with `\Skeldir Webpage`, branch `feat/discoverability-remediation`.
