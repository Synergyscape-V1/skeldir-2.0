#!/usr/bin/env node

/**
 * D2 Scope Boundary Validator
 *
 * Non-vacuous validation of D2 authority boundary coherence.
 * Ensures D2_SCOPE.md ↔ src/components/composites/index.ts are synchronized.
 *
 * Falsifiable invariants:
 * 1. Every D2-authoritative component in scope manifest MUST be exported in barrel
 * 2. Every export in barrel MUST be declared in scope manifest
 * 3. Component files MUST exist at declared paths
 *
 * Exit codes:
 * - 0: PASS (all invariants hold)
 * - 1: FAIL (at least one invariant violated)
 *
 * Usage:
 *   node scripts/validate-d2-scope.mjs
 *   npm run validate:d2-scope
 */

import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = join(__dirname, '..');

// ============================================================================
// Configuration
// ============================================================================

const SCOPE_MANIFEST_PATH = join(projectRoot, '../docs/forensics/D2_SCOPE.md');
const BARREL_PATH = join(projectRoot, 'src/components/composites/index.ts');

// ============================================================================
// Parsers
// ============================================================================

/**
 * Extract D2-authoritative component list from scope manifest
 * Parses the "D2-Authoritative Composites" table
 */
function parseD2AuthoritativeComponents(manifestContent) {
  const components = [];

  // Find the D2-Authoritative Composites table
  const tableRegex = /### D2-Authoritative Composites.*?\n\n([\s\S]*?)\n\n/;
  const match = manifestContent.match(tableRegex);

  if (!match) {
    console.error('❌ Could not find D2-Authoritative Composites table in manifest');
    return components;
  }

  const tableContent = match[1];
  const rows = tableContent.split('\n');

  // Skip header and separator rows
  for (let i = 2; i < rows.length; i++) {
    const row = rows[i].trim();
    if (!row || row.startsWith('**Total D2')) break;

    // Extract component name from first column (e.g., "| **ActivitySection** | ...")
    const nameMatch = row.match(/\|\s*\*\*([^*]+)\*\*/);
    if (nameMatch) {
      const componentName = nameMatch[1].trim();

      // Extract location from second column
      const locationMatch = row.match(/\|\s*[^|]+\|\s*([^|]+)\|/);
      const location = locationMatch ? locationMatch[1].trim() : 'unknown';

      components.push({ name: componentName, location });
    }
  }

  return components;
}

/**
 * Extract exports from barrel index.ts
 * Parses export statements to find component names
 */
function parseBarrelExports(barrelContent) {
  const exports = [];

  // Split into lines and filter out comments
  const lines = barrelContent.split('\n');

  for (const line of lines) {
    const trimmedLine = line.trim();

    // Skip comment lines
    if (trimmedLine.startsWith('//') || trimmedLine.startsWith('/*') || trimmedLine.startsWith('*')) {
      continue;
    }

    // Match export patterns:
    // - export { ComponentName } from 'path';
    // - export { default as ComponentName } from 'path';
    const exportMatch = trimmedLine.match(/^export\s+\{\s*(?:default\s+as\s+)?(\w+)\s*\}\s+from\s+['"]([^'"]+)['"]/);

    if (exportMatch) {
      const componentName = exportMatch[1];
      const importPath = exportMatch[2];
      exports.push({ name: componentName, path: importPath });
    }
  }

  return exports;
}

/**
 * Resolve component file path from import path
 * Handles path aliases like @/components/...
 */
function resolveComponentPath(importPath) {
  // Handle @/ alias
  let resolvedPath = importPath.replace(/^@\//, 'src/');

  // Add .tsx extension if not present
  if (!resolvedPath.endsWith('.tsx') && !resolvedPath.endsWith('.ts')) {
    resolvedPath += '.tsx';
  }

  return join(projectRoot, resolvedPath);
}

// ============================================================================
// Validators
// ============================================================================

/**
 * Validate that all scope manifest components are exported in barrel
 */
function validateScopeToBarrel(scopeComponents, barrelExports) {
  const barrelNames = new Set(barrelExports.map(e => e.name));
  const missing = [];

  for (const component of scopeComponents) {
    if (!barrelNames.has(component.name)) {
      missing.push(component.name);
    }
  }

  return { valid: missing.length === 0, missing };
}

/**
 * Validate that all barrel exports are declared in scope manifest
 */
function validateBarrelToScope(barrelExports, scopeComponents) {
  const scopeNames = new Set(scopeComponents.map(c => c.name));
  const extra = [];

  for (const exportItem of barrelExports) {
    if (!scopeNames.has(exportItem.name)) {
      extra.push(exportItem.name);
    }
  }

  return { valid: extra.length === 0, extra };
}

/**
 * Validate that all component files exist at declared paths
 */
function validateFileExistence(barrelExports) {
  const missing = [];

  for (const exportItem of barrelExports) {
    const filePath = resolveComponentPath(exportItem.path);
    if (!existsSync(filePath)) {
      missing.push({ component: exportItem.name, path: filePath });
    }
  }

  return { valid: missing.length === 0, missing };
}

// ============================================================================
// Main Validator
// ============================================================================

function main() {
  console.log('🔍 D2 Scope Boundary Validator');
  console.log('================================================================================\n');

  // Check files exist
  if (!existsSync(SCOPE_MANIFEST_PATH)) {
    console.error(`❌ FAIL: Scope manifest not found at ${SCOPE_MANIFEST_PATH}`);
    process.exit(1);
  }

  if (!existsSync(BARREL_PATH)) {
    console.error(`❌ FAIL: Barrel export not found at ${BARREL_PATH}`);
    process.exit(1);
  }

  console.log(`✅ Scope manifest found: ${SCOPE_MANIFEST_PATH}`);
  console.log(`✅ Barrel export found: ${BARREL_PATH}\n`);

  // Parse files
  const manifestContent = readFileSync(SCOPE_MANIFEST_PATH, 'utf-8');
  const barrelContent = readFileSync(BARREL_PATH, 'utf-8');

  const scopeComponents = parseD2AuthoritativeComponents(manifestContent);
  const barrelExports = parseBarrelExports(barrelContent);

  console.log(`📋 Scope manifest declares: ${scopeComponents.length} D2-authoritative components`);
  console.log(`   Components: ${scopeComponents.map(c => c.name).join(', ')}`);
  console.log(`📦 Barrel exports: ${barrelExports.length} components`);
  console.log(`   Exports: ${barrelExports.map(e => e.name).join(', ')}\n`);

  if (scopeComponents.length === 0) {
    console.error('❌ FAIL: No D2 components found in scope manifest (parser error?)');
    process.exit(1);
  }

  // Run validators
  let allValid = true;

  // Invariant 1: Scope → Barrel (all declared components are exported)
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Invariant 1: All scope manifest components are exported in barrel');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  const scopeToBarrel = validateScopeToBarrel(scopeComponents, barrelExports);
  if (scopeToBarrel.valid) {
    console.log('✅ PASS: All scope components are exported in barrel\n');
  } else {
    console.error(`❌ FAIL: ${scopeToBarrel.missing.length} component(s) in scope but missing from barrel:`);
    scopeToBarrel.missing.forEach(name => console.error(`   - ${name}`));
    console.error('');
    allValid = false;
  }

  // Invariant 2: Barrel → Scope (no unauthorized exports)
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Invariant 2: All barrel exports are declared in scope manifest');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  const barrelToScope = validateBarrelToScope(barrelExports, scopeComponents);
  if (barrelToScope.valid) {
    console.log('✅ PASS: All barrel exports are declared in scope manifest\n');
  } else {
    console.error(`❌ FAIL: ${barrelToScope.extra.length} component(s) exported but not in scope manifest:`);
    barrelToScope.extra.forEach(name => console.error(`   - ${name}`));
    console.error('');
    allValid = false;
  }

  // Invariant 3: File Existence (all export paths resolve to real files)
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('Invariant 3: All component files exist at declared paths');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  const fileExistence = validateFileExistence(barrelExports);
  if (fileExistence.valid) {
    console.log('✅ PASS: All component files exist\n');
  } else {
    console.error(`❌ FAIL: ${fileExistence.missing.length} component file(s) not found:`);
    fileExistence.missing.forEach(({ component, path }) => {
      console.error(`   - ${component}: ${path}`);
    });
    console.error('');
    allValid = false;
  }

  // Summary
  console.log('================================================================================');
  if (allValid) {
    console.log('✅ D2 SCOPE BOUNDARY VALIDATION: PASS');
    console.log('================================================================================\n');
    console.log('All invariants hold. D2 authority boundary is coherent.');
    console.log('Manifest ↔ Barrel are synchronized, all files exist.\n');
    process.exit(0);
  } else {
    console.log('❌ D2 SCOPE BOUNDARY VALIDATION: FAIL');
    console.log('================================================================================\n');
    console.log('One or more invariants violated. Fix the issues above and re-run.\n');
    process.exit(1);
  }
}

main();
