#!/usr/bin/env node

/**
 * D2 Composition Integrity Validator (D2-P1)
 *
 * Non-vacuous validation that D2-authoritative composites compose D1 atoms
 * correctly and do not contain silent UI bypasses.
 *
 * Falsifiable invariants:
 * 1. Every D2 composite (except exception-tagged) MUST import at least one D1 atom
 * 2. No D2 composite may import from forbidden tiers (pages/screens/features)
 * 3. D2 composites must NOT use raw <button>/<input>/<textarea>/<select> elements
 *    when D1 equivalents exist (Button/Input/Textarea/Select), unless exception-tagged
 *
 * Exception registry: Read from D2_SCOPE.md §9 "Bypass Exception Registry"
 *
 * Exit codes:
 * - 0: PASS (all invariants hold)
 * - 1: FAIL (at least one invariant violated)
 *
 * Usage:
 *   node scripts/validate-d2-composition.mjs
 *   npm run validate:d2-composition
 */

import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = join(__dirname, '..');

// ============================================================================
// Configuration
// ============================================================================

const D1_ATOM_PATH_PREFIX = '@/components/ui/';
const BARREL_PATH = join(projectRoot, 'src', 'components', 'composites', 'index.ts');
const SCOPE_MANIFEST_PATH = join(projectRoot, '..', 'docs', 'forensics', 'D2_SCOPE.md');

// D1 atoms that have raw HTML equivalents
const D1_ATOM_HTML_EQUIVALENTS = {
  button: 'Button (@/components/ui/button)',
  input: 'Input (@/components/ui/input)',
  textarea: 'Textarea (@/components/ui/textarea)',
  select: 'Select (@/components/ui/select)',
};

// Forbidden import path patterns (screen/page/feature tier)
const FORBIDDEN_IMPORT_PATTERNS = [
  /from ['"]@\/pages\//,
  /from ['"]@\/screens\//,
  /from ['"]@\/features\//,
  /from ['"]\.\.\/pages\//,
  /from ['"]\.\.\/screens\//,
];

// ============================================================================
// Parsers
// ============================================================================

/**
 * Parse the barrel export to extract component names and their source file paths
 */
function parseBarrelExports(barrelContent) {
  const exports = [];
  const lines = barrelContent.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('//') || trimmed === '') continue;

    // Match: export { X } from 'path'
    const namedMatch = trimmed.match(/export\s*\{\s*(\w+)\s*\}\s*from\s*['"]([^'"]+)['"]/);
    if (namedMatch) {
      exports.push({ name: namedMatch[1], importPath: namedMatch[2] });
      continue;
    }

    // Match: export { default as X } from 'path'
    const defaultMatch = trimmed.match(/export\s*\{\s*default\s+as\s+(\w+)\s*\}\s*from\s*['"]([^'"]+)['"]/);
    if (defaultMatch) {
      exports.push({ name: defaultMatch[1], importPath: defaultMatch[2] });
    }
  }

  return exports;
}

/**
 * Resolve @/ alias to absolute file path
 */
function resolveImportPath(importPath) {
  if (importPath.startsWith('@/')) {
    const relative = importPath.replace('@/', '');
    const withExt = relative.endsWith('.tsx') || relative.endsWith('.ts')
      ? relative
      : relative + '.tsx';
    return join(projectRoot, 'src', withExt);
  }
  return importPath;
}

/**
 * Extract all import statements from a TSX/TS file
 */
function extractImports(fileContent) {
  const imports = [];
  const importRegex = /import\s+(?:(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+\w+|\w+))*\s+from\s+)?['"]([^'"]+)['"]/g;

  let match;
  while ((match = importRegex.exec(fileContent)) !== null) {
    imports.push(match[1]);
  }

  // Also catch: import 'file.css' style imports
  const sideEffectRegex = /import\s+['"]([^'"]+)['"]/g;
  while ((match = sideEffectRegex.exec(fileContent)) !== null) {
    if (!imports.includes(match[1])) {
      imports.push(match[1]);
    }
  }

  return imports;
}

/**
 * Check if file content uses raw HTML elements that should be D1 atoms
 * Returns array of { element, line, d1Equivalent }
 */
function detectRawHtmlBypasses(fileContent, fileName) {
  const bypasses = [];
  const lines = fileContent.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lineNum = i + 1;

    // Skip comments and strings (simple heuristic)
    const trimmed = line.trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('/*')) continue;

    // Detect raw <button in JSX (not inside comments or strings)
    if (/<button[\s/>]/.test(line) && !/<Button[\s/>]/.test(line)) {
      bypasses.push({ element: 'button', line: lineNum, d1Equivalent: D1_ATOM_HTML_EQUIVALENTS.button });
    }

    // Detect raw <input in JSX
    if (/<input[\s/>]/.test(line) && !/<Input[\s/>]/.test(line)) {
      bypasses.push({ element: 'input', line: lineNum, d1Equivalent: D1_ATOM_HTML_EQUIVALENTS.input });
    }

    // Detect raw <textarea in JSX
    if (/<textarea[\s/>]/.test(line) && !/<Textarea[\s/>]/.test(line)) {
      bypasses.push({ element: 'textarea', line: lineNum, d1Equivalent: D1_ATOM_HTML_EQUIVALENTS.textarea });
    }

    // Detect raw <select in JSX (exception-tagged in BulkActionModal)
    if (/<select[\s/>]/.test(line) && !/<Select[\s/>]/.test(line)) {
      // Check for exception comment on preceding lines
      const contextStart = Math.max(0, i - 5);
      const context = lines.slice(contextStart, i + 1).join('\n');
      if (/Exception-tagged|EXC-\d+|Native <select> retained/.test(context)) {
        // Exception tagged - skip
        continue;
      }
      bypasses.push({ element: 'select', line: lineNum, d1Equivalent: D1_ATOM_HTML_EQUIVALENTS.select });
    }
  }

  return bypasses;
}

/**
 * Parse exception registry from D2_SCOPE.md
 * Returns Set of component names that have full D1 bypass exceptions
 */
function parseExceptionRegistry(scopeContent) {
  const exceptions = new Map(); // componentName -> { id, scope }

  // Match EXC-NNN entries
  const excRegex = /### (EXC-\d+):\s*(\w+)\s*—\s*(.*)/g;
  let match;
  while ((match = excRegex.exec(scopeContent)) !== null) {
    const id = match[1];
    const component = match[2];
    const description = match[3];

    // Check if it's a "Full D1 Bypass"
    const isFullBypass = /Full D1 Bypass/.test(description);
    // Check if it's a "Structural" bypass
    const isStructural = /Structural D1 Bypass/.test(description);
    // Check if it's a specific element bypass
    const isElementBypass = /Native.*<\w+>/.test(description);

    exceptions.set(component, {
      id,
      description,
      fullBypass: isFullBypass,
      structuralBypass: isStructural,
      elementBypass: isElementBypass,
    });
  }

  return exceptions;
}

/**
 * Classify an import path into a tier
 */
function classifyImport(importPath) {
  if (importPath.startsWith('@/components/ui/')) return 'D1_ATOM';
  if (importPath.startsWith('@/lib/')) return 'D0_UTILITY';
  if (importPath.startsWith('@/hooks/')) return 'HOOK';
  if (importPath.startsWith('@/contexts/')) return 'CONTEXT';
  if (importPath.startsWith('@/types/')) return 'TYPE';
  if (importPath.startsWith('@shared/')) return 'SHARED_TYPE';
  if (importPath.startsWith('@/components/icons') || importPath.startsWith('@/components/common/')) return 'ALLOWED_COMPONENT';
  if (importPath.startsWith('@/components/error-banner/') || importPath.startsWith('./')) return 'SIBLING';
  if (importPath.startsWith('@/components/composites')) return 'D2_BARREL';
  if (importPath.startsWith('@/components/')) return 'OTHER_COMPONENT';
  if (importPath.startsWith('@/pages/') || importPath.startsWith('@/screens/') || importPath.startsWith('@/features/')) return 'FORBIDDEN';
  if (importPath.endsWith('.css')) return 'STYLE';
  if (!importPath.startsWith('@/') && !importPath.startsWith('.')) return 'EXTERNAL';
  return 'UNKNOWN';
}

// ============================================================================
// Main Validation
// ============================================================================

function main() {
  console.log('🔍 D2 Composition Integrity Validator (D2-P1)');
  console.log('='.repeat(80));
  console.log();

  let hasFailure = false;

  // 1. Load barrel exports
  if (!existsSync(BARREL_PATH)) {
    console.log('❌ Barrel export not found:', BARREL_PATH);
    process.exit(1);
  }

  const barrelContent = readFileSync(BARREL_PATH, 'utf-8');
  const barrelExports = parseBarrelExports(barrelContent);
  console.log(`📦 Barrel exports: ${barrelExports.length} D2 composites`);

  // 2. Load exception registry
  let exceptions = new Map();
  if (existsSync(SCOPE_MANIFEST_PATH)) {
    const scopeContent = readFileSync(SCOPE_MANIFEST_PATH, 'utf-8');
    exceptions = parseExceptionRegistry(scopeContent);
    console.log(`📋 Exception registry: ${exceptions.size} exception(s) loaded`);
    for (const [comp, exc] of exceptions) {
      console.log(`   - ${exc.id}: ${comp} (${exc.fullBypass ? 'full bypass' : exc.structuralBypass ? 'structural' : 'element'})`);
    }
  } else {
    console.log('⚠️  Scope manifest not found, no exceptions loaded');
  }

  console.log();

  // 3. Validate each D2 composite
  console.log('━'.repeat(80));
  console.log('Invariant 1: D2 composites must import D1 atoms (unless exception-tagged)');
  console.log('━'.repeat(80));
  console.log();

  let inv1Pass = true;
  const bomEntries = [];

  for (const exp of barrelExports) {
    const filePath = resolveImportPath(exp.importPath);

    // Try .tsx and .ts
    let actualPath = filePath;
    if (!existsSync(actualPath)) {
      actualPath = filePath.replace('.tsx', '.ts');
    }
    if (!existsSync(actualPath)) {
      console.log(`   ⚠️  ${exp.name}: File not found at ${filePath}`);
      continue;
    }

    const content = readFileSync(actualPath, 'utf-8');
    const imports = extractImports(content);
    const classified = imports.map(imp => ({ path: imp, tier: classifyImport(imp) }));
    const d1Imports = classified.filter(c => c.tier === 'D1_ATOM');

    const exception = exceptions.get(exp.name);
    const isFullException = exception?.fullBypass;

    // Orchestration-only components (Provider, Container) may not need D1 imports
    const isOrchestration = /Provider|Container/.test(exp.name);

    const bomEntry = {
      name: exp.name,
      path: exp.importPath,
      imports: classified,
      d1Count: d1Imports.length,
      exception: exception || null,
      isOrchestration,
    };
    bomEntries.push(bomEntry);

    if (d1Imports.length === 0 && !isFullException && !isOrchestration) {
      console.log(`   ❌ ${exp.name}: No D1 atom imports found`);
      console.log(`      Imports: ${imports.join(', ')}`);
      inv1Pass = false;
      hasFailure = true;
    } else if (isFullException) {
      console.log(`   🏷️  ${exp.name}: Exception-tagged (${exception.id}) — D1 import check skipped`);
    } else if (isOrchestration) {
      console.log(`   ℹ️  ${exp.name}: Orchestration component — D1 import check N/A`);
    } else {
      console.log(`   ✅ ${exp.name}: ${d1Imports.length} D1 atom(s) imported`);
      for (const d1 of d1Imports) {
        console.log(`      └─ ${d1.path}`);
      }
    }
  }

  console.log();
  console.log(inv1Pass ? '✅ PASS: All non-exception D2 composites import D1 atoms' : '❌ FAIL: Some D2 composites lack D1 atom imports');
  console.log();

  // 4. Check forbidden imports
  console.log('━'.repeat(80));
  console.log('Invariant 2: No D2 composite imports from forbidden tiers');
  console.log('━'.repeat(80));
  console.log();

  let inv2Pass = true;

  for (const bom of bomEntries) {
    const forbidden = bom.imports.filter(c => c.tier === 'FORBIDDEN');
    if (forbidden.length > 0) {
      console.log(`   ❌ ${bom.name}: Forbidden imports detected`);
      for (const f of forbidden) {
        console.log(`      └─ ${f.path}`);
      }
      inv2Pass = false;
      hasFailure = true;
    }
  }

  if (inv2Pass) {
    console.log('   ✅ No forbidden tier imports detected');
  }

  console.log();
  console.log(inv2Pass ? '✅ PASS: No forbidden imports in D2 composites' : '❌ FAIL: Forbidden imports found');
  console.log();

  // 5. Check raw HTML element bypasses
  console.log('━'.repeat(80));
  console.log('Invariant 3: No silent raw HTML bypasses (button/input/textarea/select)');
  console.log('━'.repeat(80));
  console.log();

  let inv3Pass = true;

  for (const exp of barrelExports) {
    const filePath = resolveImportPath(exp.importPath);
    let actualPath = filePath;
    if (!existsSync(actualPath)) {
      actualPath = filePath.replace('.tsx', '.ts');
    }
    if (!existsSync(actualPath)) continue;

    const content = readFileSync(actualPath, 'utf-8');
    const exception = exceptions.get(exp.name);

    // Skip full-exception components
    if (exception?.fullBypass) {
      console.log(`   🏷️  ${exp.name}: Exception-tagged (${exception.id}) — HTML bypass check skipped`);
      continue;
    }

    // Skip orchestration components
    if (/Provider|Container/.test(exp.name)) {
      console.log(`   ℹ️  ${exp.name}: Orchestration component — HTML bypass check N/A`);
      continue;
    }

    const bypasses = detectRawHtmlBypasses(content, exp.name);

    if (bypasses.length > 0) {
      console.log(`   ❌ ${exp.name}: ${bypasses.length} raw HTML bypass(es) detected`);
      for (const b of bypasses) {
        console.log(`      └─ Line ${b.line}: <${b.element}> → should use ${b.d1Equivalent}`);
      }
      inv3Pass = false;
      hasFailure = true;
    } else {
      console.log(`   ✅ ${exp.name}: No raw HTML bypasses`);
    }
  }

  console.log();
  console.log(inv3Pass ? '✅ PASS: No silent raw HTML bypasses in D2 composites' : '❌ FAIL: Raw HTML bypasses found');
  console.log();

  // 6. Print BOM summary
  console.log('━'.repeat(80));
  console.log('BOM Summary (Bill of Materials per D2 composite)');
  console.log('━'.repeat(80));
  console.log();

  for (const bom of bomEntries) {
    const d1 = bom.imports.filter(c => c.tier === 'D1_ATOM').map(c => c.path);
    const d0 = bom.imports.filter(c => c.tier === 'D0_UTILITY').map(c => c.path);
    const ext = bom.imports.filter(c => c.tier === 'EXTERNAL').map(c => c.path);
    const other = bom.imports.filter(c => !['D1_ATOM', 'D0_UTILITY', 'EXTERNAL', 'STYLE'].includes(c.tier)).map(c => `${c.path} [${c.tier}]`);

    console.log(`   📦 ${bom.name} (${bom.path})`);
    if (bom.exception) console.log(`      🏷️  Exception: ${bom.exception.id}`);
    if (d1.length > 0) console.log(`      D1 atoms: ${d1.join(', ')}`);
    if (d0.length > 0) console.log(`      D0 utils: ${d0.join(', ')}`);
    if (ext.length > 0) console.log(`      External: ${ext.join(', ')}`);
    if (other.length > 0) console.log(`      Other: ${other.join(', ')}`);
    console.log();
  }

  // 7. Final verdict
  console.log('='.repeat(80));
  if (hasFailure) {
    console.log('❌ D2 COMPOSITION INTEGRITY VALIDATION: FAIL');
    console.log('='.repeat(80));
    console.log();
    console.log('One or more invariants violated. Fix the issues above and re-run.');
    process.exit(1);
  } else {
    console.log('✅ D2 COMPOSITION INTEGRITY VALIDATION: PASS');
    console.log('='.repeat(80));
    console.log();
    console.log('All invariants hold. D2 composites correctly compose D1 atoms.');
    console.log('Exception-tagged bypasses are explicitly documented in D2_SCOPE.md §9.');
    process.exit(0);
  }
}

main();
