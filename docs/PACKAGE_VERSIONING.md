# Package Versioning & Update Procedures

## Version Coupling Requirement

The Skeldir frontend integration requires **strict version coupling** between two packages:

```
@muk223/openapi-contracts === @muk223/api-client
```

**Critical Rule**: These packages MUST always be the same version. Any version drift will cause:
- Runtime contract violations
- Type mismatches
- API call failures
- Binary Gate 6 failure (blocks integration)

---

## Current Versions

- `@muk223/openapi-contracts@2.0.7`
- `@muk223/api-client@2.0.7`

---

## Why Version Coupling Matters

The `@muk223/api-client` SDK is **auto-generated** from the contracts in `@muk223/openapi-contracts`. This means:

1. **Contract Update** → Backend team updates OpenAPI specs
2. **SDK Generation** → CI generates new TypeScript SDK from contracts
3. **Package Publish** → Both packages published with **same version**
4. **Frontend Update** → Frontend must update **both packages together**

**Example of drift problem:**

```json
// ❌ BAD - Version drift
{
  "@muk223/openapi-contracts": "2.0.7",
  "@muk223/api-client": "2.1.0"  // SDK ahead of contracts
}

// Result: SDK expects endpoints/schemas that don't exist in contracts
```

```json
// ✅ GOOD - Versions synchronized
{
  "@muk223/openapi-contracts": "2.0.7",
  "@muk223/api-client": "2.0.7"
}
```

---

## Package Update Procedure

### Step 1: Check for New Versions

```bash
# Check NPM registry for updates
npm view @muk223/openapi-contracts versions --json
npm view @muk223/api-client versions --json

# Or check with npm outdated
npm outdated @muk223/openapi-contracts @muk223/api-client
```

### Step 2: Update Both Packages Together

**Always update both packages in a single command:**

```bash
# Update to specific version (recommended)
npm install @muk223/openapi-contracts@2.1.0 @muk223/api-client@2.1.0

# Or update to latest (only if versions match)
npm install @muk223/openapi-contracts@latest @muk223/api-client@latest
```

**Never update one package alone:**

```bash
# ❌ NEVER DO THIS
npm install @muk223/openapi-contracts@2.1.0  # Alone
npm install @muk223/api-client@2.0.7         # Different version
```

### Step 3: Regenerate Checksums

After updating contracts, regenerate checksums:

```bash
node scripts/generate-checksums.js
```

This updates `checksums.json` with new SHA256 hashes.

### Step 4: Validate Changes

```bash
# Validate checksums
node scripts/validate-checksums.js

# Restart mock servers with new contracts
bash scripts/mock-docker-start.sh

# Run health checks
node scripts/mock-health-check.js

# Run contract tests
npm run test:contracts
```

### Step 5: Check for Breaking Changes

```bash
# Install openapi-diff if not present
npm install -g openapi-diff

# Compare old vs new contracts
openapi-diff \
  node_modules/@muk223/openapi-contracts-old/contracts/attribution.yaml \
  node_modules/@muk223/openapi-contracts/contracts/attribution.yaml
```

If breaking changes detected:
- Update SDK calls in codebase
- Update types/interfaces
- Update tests
- Document migration steps

### Step 6: Update Documentation

Update version references in:
- `README.md`
- `docs/CONTRACTS_QUICKSTART.md`
- `docs/FRONTEND_INTEGRATION.md`
- This file (`docs/PACKAGE_VERSIONING.md`)

### Step 7: Commit Changes

```bash
# Add all changes
git add package.json package-lock.json checksums.json docs/

# Commit with descriptive message
git commit -m "chore: update @muk223 packages to v2.1.0

- Updated @muk223/openapi-contracts@2.1.0
- Updated @muk223/api-client@2.1.0
- Regenerated checksums.json
- Validated mock servers and tests
- No breaking changes detected"

# Push changes
git push origin feature/update-skeldir-packages
```

---

## Version Validation Script

Create `scripts/validate-versions.js`:

```javascript
#!/usr/bin/env node

import { readFileSync } from 'fs';

const pkg = JSON.parse(readFileSync('./package.json', 'utf8'));

const contractsVersion = pkg.dependencies?.['@muk223/openapi-contracts'];
const clientVersion = pkg.dependencies?.['@muk223/api-client'];

console.log('📦 @muk223/openapi-contracts:', contractsVersion);
console.log('📦 @muk223/api-client:', clientVersion);

if (!contractsVersion || !clientVersion) {
  console.error('❌ Missing @muk223 packages');
  process.exit(1);
}

if (contractsVersion !== clientVersion) {
  console.error('❌ VERSION MISMATCH DETECTED');
  console.error(`   Contracts: ${contractsVersion}`);
  console.error(`   Client: ${clientVersion}`);
  console.error('');
  console.error('Fix: npm install @muk223/openapi-contracts@X.X.X @muk223/api-client@X.X.X');
  process.exit(1);
}

console.log('✅ Package versions synchronized');
process.exit(0);
```

Run validation:

```bash
node scripts/validate-versions.js
```

---

## CI/CD Integration

The `.github/workflows/version-coupling.yml` workflow automatically validates version coupling on every PR:

```yaml
- name: Check package versions
  run: node scripts/validate-versions.js
```

**PR will be blocked if:**
- Versions don't match
- Only one package updated
- Version drift detected

---

## Rollback Procedure

If a package update causes issues:

### Option 1: Revert to Previous Version

```bash
# Revert to last known good version
npm install @muk223/openapi-contracts@2.0.7 @muk223/api-client@2.0.7

# Regenerate checksums
node scripts/generate-checksums.js

# Validate
node scripts/validate-checksums.js
```

### Option 2: Git Revert

```bash
# Revert the update commit
git revert <commit-hash>

# Reinstall dependencies
npm install
```

---

## Offline Installation (Tarball)

For environments without NPM registry access:

### Step 1: Download Tarballs

```bash
# From machine with internet access
npm pack @muk223/openapi-contracts@2.0.7
npm pack @muk223/api-client@2.0.7

# This creates:
# - skeldir-openapi-contracts-2.0.7.tgz
# - skeldir-api-client-2.0.7.tgz
```

### Step 2: Transfer Tarballs

Copy tarball files to offline environment

### Step 3: Install from Tarball

```bash
# Install both packages
npm install skeldir-openapi-contracts-2.0.7.tgz
npm install skeldir-api-client-2.0.7.tgz

# Verify installation
npm list @muk223/openapi-contracts @muk223/api-client
```

### Step 4: Validate

```bash
# Check contracts present
ls node_modules/@muk223/openapi-contracts/contracts/

# Regenerate checksums if needed
node scripts/generate-checksums.js
```

---

## NPM Registry Configuration

### GitHub Package Registry

If packages are hosted on GitHub Package Registry:

```bash
# Create .npmrc
echo "@muk223:registry=https://npm.pkg.github.com" >> .npmrc

# Authenticate
npm login --scope=@muk223 --registry=https://npm.pkg.github.com
```

### Private NPM Registry

```bash
# Configure registry
npm config set @muk223:registry https://registry.skeldir.com

# Authenticate with token
npm config set //registry.skeldir.com/:_authToken ${NPM_TOKEN}
```

---

## Version History

| Version | Release Date | Changes | Breaking |
|---------|--------------|---------|----------|
| 2.0.7 | 2025-10-01 | Initial contract-first release | N/A |
| 2.0.7 | TBD | Bug fixes | No |
| 2.1.0 | TBD | New webhook endpoints | No |

---

## Troubleshooting

### "Packages not found" error

```bash
# Check registry configuration
npm config list

# Verify authentication
npm whoami --registry=https://npm.pkg.github.com
```

### "Version mismatch" in CI

```bash
# Locally validate versions match
node scripts/validate-versions.js

# Update both packages to same version
npm install @muk223/openapi-contracts@X.X.X @muk223/api-client@X.X.X
```

### "Checksum validation failed" after update

```bash
# Regenerate checksums with new contract files
node scripts/generate-checksums.js

# Commit updated checksums.json
git add checksums.json
git commit -m "chore: update checksums for v2.1.0"
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Check versions | `npm list @muk223/openapi-contracts @muk223/api-client` |
| Update both | `npm install @muk223/openapi-contracts@X.X.X @muk223/api-client@X.X.X` |
| Validate sync | `node scripts/validate-versions.js` |
| Regenerate checksums | `node scripts/generate-checksums.js` |
| Check for breaking | `openapi-diff old.yaml new.yaml` |
| Create tarball | `npm pack @muk223/openapi-contracts` |
| Install from tarball | `npm install package.tgz` |

---

**Remember**: Always update both packages together. Never let versions drift.
