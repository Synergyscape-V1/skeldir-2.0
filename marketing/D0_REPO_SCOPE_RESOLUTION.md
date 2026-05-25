# D0 Repo Scope Resolution

**Phase:** D0 Corrective Action  
**Date:** 2026-05-21  
**Purpose:** Resolve which worktree is authoritative for D1 and eventual D10 commit/push.

---

## 1. Command Evidence

### Working directory (D0 artifact location)

```text
C:\Users\ayewhy\Skeldir Webpage\marketing
```

All D0 artifacts live in this directory. This is the **authoritative D1 worktree** for discoverability remediation.

### Git root (from `marketing/`)

```bash
$ git rev-parse --show-toplevel
C:/Users/ayewhy
```

**Finding:** Git is initialized at the user home directory, not at `Skeldir Webpage/` or `marketing/`. This is **mis-scoped** and must be corrected before D10 commit/push.

### Workspace root git

```bash
$ test -d "C:/Users/ayewhy/Skeldir Webpage/.git"
NO — no .git in Skeldir Webpage/
```

### Current branch

```bash
$ git branch --show-current
master
```

### Remote

```bash
$ git remote -v
origin  https://github.com/Muk223/skeldir-2.0.git (fetch)
origin  https://github.com/Muk223/skeldir-2.0.git (push)
```

### Remote HEAD

```bash
$ git symbolic-ref refs/remotes/origin/HEAD
fatal: ref refs/remotes/origin/HEAD is not a symbolic ref
```

**Finding:** No commits exist locally; remote HEAD cannot be resolved. Branch `master` has zero commits.

### Netlify deploy configuration (production clone)

```bash
$ find . -maxdepth 3 -name "netlify.toml"
./skeldir-production-main-deploy-20260518/netlify.toml
```

```toml
# skeldir-production-main-deploy-20260518/netlify.toml
[build]
  base = "marketing"
  command = "npm run build"
  publish = "out"
```

### Production-deployed git clone

```bash
$ git -C skeldir-production-main-deploy-20260518 rev-parse --show-toplevel
C:/Users/ayewhy/Skeldir Webpage/skeldir-production-main-deploy-20260518

$ git -C skeldir-production-main-deploy-20260518 branch --show-current
codex/marketing-production-missing-lib

$ git -C skeldir-production-main-deploy-20260518 remote -v
origin  https://github.com/Synergyscape-V1/skeldir-2.0.git

$ git -C skeldir-production-main-deploy-20260518 log -1 --oneline
43921ca6 Add ignored marketing metadata sources
```

---

## 2. Authority Determination

| Question | Answer |
|---|---|
| Where were D0 artifacts created? | `C:\Users\ayewhy\Skeldir Webpage\marketing\` |
| Which tree should D1 modify? | **Same tree:** `Skeldir Webpage/marketing/` |
| Is this the production deploy source? | **Likely yes** — Netlify `base=marketing`, `publish=out` matches this layout |
| Is the production clone authoritative for code? | **Reference only** — `skeldir-production-main-deploy-20260518/` is a snapshot clone on `Synergyscape-V1/skeldir-2.0.git`, branch `codex/marketing-production-missing-lib` |
| Are stale clones deployable sources? | **No** — classified non-authoritative (see below) |
| Can D0 artifacts be committed now? | **No** — deferred to D10 per user instruction; git scope must be fixed first |

---

## 3. Stale / Non-Authoritative Directories

These directories must **not** receive D1 fixes unless explicitly re-designated:

| Directory | Classification | Reason |
|---|---|---|
| `skeldir-deploy-clean/` | Non-authoritative stale clone | Older deploy experiment |
| `skeldir-favicon-clean/` | Non-authoritative stale clone | Favicon-only fork |
| `skeldir-netlify-fix-20260430/` | Non-authoritative stale clone | Netlify fix snapshot |
| `skeldir-2.0-clone/` | Non-authoritative stale clone | Generic clone copy |
| `skeldir-production-main-deploy-20260518/` | Production reference clone | Used to verify Netlify config and deployed commit; not active dev tree |

---

## 4. D10 Handoff Note (Commit/Push Deferred)

When commit/push is authorized at D10:

1. **Fix git scope** — Initialize or re-root git at `Skeldir Webpage/` (or `marketing/`) so commits do not encompass the user home directory.
2. **Confirm deploy remote** — Verify whether production Netlify deploys from `Synergyscape-V1/skeldir-2.0` or `Muk223/skeldir-2.0`.
3. **Primary branch** — Record actual primary branch (`main` vs `master`) from remote after first push.
4. **D0 artifact commit** — Commit all files listed in `Phase D0 Corrective Action Completion Report.md` section 4.
5. **Post-commit proof** — Run `npm run discoverability:d0` and `npm run discoverability:d0:negative-controls` after commit.

---

## 5. Unresolved Repo/Deploy Unknowns

| Unknown | Owner | Required By |
|---|---|---|
| Which GitHub org Netlify production actually deploys from | Infrastructure | D10 |
| Whether `www.skeldir.com` is a separate deploy surface | Infrastructure | D2 |
| Whether local `Muk223/skeldir-2.0` and `Synergyscape-V1/skeldir-2.0` are synced | Infrastructure | D10 |
| Correct primary branch name after git re-scope | Infrastructure | D10 |

---

## 6. Gate C-D0.1 Status

**Met for D1 purposes:** Yes — authoritative D1 worktree is identified as `Skeldir Webpage/marketing/`.

**Not met for D10 purposes:** Git scope is misconfigured; no commits exist; push target ambiguous between two GitHub orgs.
