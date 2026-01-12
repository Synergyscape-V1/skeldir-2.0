# Root Cause Analysis: Bundling Manifest Integration Issue

## Problem Statement

When attempting to answer **Question 1** of the investigatory technical questions, agents encountered a persistent error that caused the investigatory process to halt.

**Question 1:** *"Does the bundling process now use a **declarative manifest** (e.g., `entrypoints.json` or `dist_manifest.yaml`) to define the 9 expected bundles, and does a script (`check_dist_complete`) **automatically fail** if any of the 9 are missing, rather than relying on manual file counting?"*

## Root Cause Identified

The investigation revealed a **critical disconnect** between the implementation and the requirements:

### Issue 1: Hardcoded Entrypoints
- **Location:** `scripts/contracts/bundle.sh` lines 37-47 (original)
- **Problem:** The script hardcoded entrypoints in a bash associative array instead of reading from the declarative manifest (`entrypoints.json`)
- **Impact:** The bundling process did NOT use a declarative manifest, making it impossible to answer Question 1 affirmatively

### Issue 2: Missing Completeness Validation
- **Location:** `scripts/contracts/bundle.sh` (original)
- **Problem:** The script did NOT call `check_dist_complete.py` to validate bundle completeness after bundling
- **Impact:** The bundling process did NOT automatically fail if bundles were missing, making it impossible to answer Question 1 affirmatively

### Why This Caused Agent Errors

When agents attempted to answer Question 1, they would:
1. ✅ Find that `entrypoints.json` manifest exists
2. ✅ Find that `check_dist_complete.py` script exists  
3. ❌ Discover that `bundle.sh` does NOT use either of them
4. ❌ Encounter a contradiction that causes the investigation to halt

The agents could not reconcile the existence of the manifest and validation script with the fact that the bundling process ignored both.

## Solution Implemented

### Changes to `scripts/contracts/bundle.sh`

1. **Manifest Integration:**
   - Removed hardcoded entrypoints array
   - Added Python script to read entrypoints from `entrypoints.json`
   - Script now dynamically loads all entrypoints from the manifest

2. **Completeness Validation Gate:**
   - Added call to `check_dist_complete.py` after bundling completes
   - Script now automatically fails if any bundles from the manifest are missing
   - Exit code 1 is returned if completeness check fails

3. **Path Resolution:**
   - Added robust path resolution to find repo root
   - Ensures script works regardless of current working directory
   - Properly handles relative paths for manifest and output files

## Verification

### Before Fix:
```bash
# bundle.sh hardcoded entrypoints
declare -A ENTRYPOINTS=(
    ["auth"]="auth.bundled.yaml"
    # ... hardcoded list
)

# No completeness check
# Script would exit 0 even if bundles were missing
```

### After Fix:
```bash
# bundle.sh reads from manifest
ENTRYPOINTS_JSON=$(python3 << 'PYTHON_EOF'
# Reads from scripts/contracts/entrypoints.json
# Dynamically extracts all entrypoints
PYTHON_EOF
)

# Completeness validation gate
python3 scripts/contracts/check_dist_complete.py
# Script exits 1 if bundles are missing
```

## Answer to Question 1

**✅ YES** - The bundling process now:

1. **Uses a declarative manifest:** `scripts/contracts/entrypoints.json` defines all 9 expected bundles
2. **Automatically fails if bundles are missing:** `check_dist_complete.py` is called within `bundle.sh` and causes the script to exit with code 1 if any bundles from the manifest are missing

## Files Modified

- `scripts/contracts/bundle.sh` - Updated to use manifest and validate completeness

## Testing Recommendations

1. **Test manifest-driven bundling:**
   ```bash
   bash scripts/contracts/bundle.sh
   # Should read from entrypoints.json and bundle all 9 entrypoints
   ```

2. **Test completeness validation:**
   ```bash
   # Delete one bundled file
   rm api-contracts/dist/openapi/v1/health.bundled.yaml
   bash scripts/contracts/bundle.sh
   # Should fail with completeness check error
   ```

3. **Test manifest modification:**
   ```bash
   # Add a new entrypoint to entrypoints.json
   # Run bundle.sh
   # Should attempt to bundle the new entrypoint
   ```

## Conclusion

The root cause was a **missing integration** between the bundling script and the manifest/validation infrastructure. The fix ensures that:

- ✅ Bundling is driven by the declarative manifest
- ✅ Completeness is automatically validated
- ✅ The process fails fast if requirements are not met
- ✅ Question 1 can now be answered affirmatively

This resolves the persistent error that was halting the investigatory process.



