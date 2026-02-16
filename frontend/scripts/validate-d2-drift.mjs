#!/usr/bin/env node

/**
 * D2 Token Drift Sentinel Scanner
 *
 * Scans D2-authoritative composites for token violations:
 * 1. Hardcoded hex literals (#[0-9a-fA-F]{3,8})
 * 2. Tailwind arbitrary hex classes (text-[#...], bg-[#...], etc.)
 * 3. Theming inline styles without justification comments
 *
 * Companion CSS files (imported via './ComponentName.css') are also scanned.
 *
 * Exit codes:
 * - 0: PASS (zero violations)
 * - 1: FAIL (one or more violations)
 *
 * Usage:
 *   node scripts/validate-d2-drift.mjs
 *   npm run validate:d2-drift
 */

import { readFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = join(__dirname, '..');

// ============================================================================
// D2 Authoritative Scope (from D2_SCOPE.md)
// ============================================================================

const D2_COMPONENTS = [
  { name: 'ActivitySection', path: 'src/components/dashboard/ActivitySection.tsx' },
  { name: 'UserInfoCard', path: 'src/components/dashboard/UserInfoCard.tsx' },
  { name: 'DataConfidenceBar', path: 'src/components/dashboard/DataConfidenceBar.tsx' },
  { name: 'BulkActionModal', path: 'src/components/dashboard/BulkActionModal.tsx' },
  { name: 'BulkActionToolbar', path: 'src/components/dashboard/BulkActionToolbar.tsx' },
  { name: 'ErrorBanner', path: 'src/components/error-banner/ErrorBanner.tsx' },
  { name: 'ErrorBannerContainer', path: 'src/components/error-banner/ErrorBannerContainer.tsx' },
  { name: 'ErrorBannerProvider', path: 'src/components/error-banner/ErrorBannerProvider.tsx' },
  { name: 'ConfidenceScoreBadge', path: 'src/components/ConfidenceScoreBadge.tsx' },
];

// ============================================================================
// Scan Patterns
// ============================================================================

// Hex literal: #followed by 3-8 hex digits (word boundary to avoid CSS selectors)
const HEX_LITERAL = /#[0-9a-fA-F]{3,8}\b/g;

// Tailwind arbitrary hex classes
const ARB_HEX_CLASS = /(?:text|bg|border|fill|stroke|ring|shadow|outline|from|to|via)-\[#[0-9a-fA-F]{3,8}\]/g;

// Theming inline style keys (non-geometry)
const THEMING_STYLE_KEYS = /\b(?:color|background(?:Color)?|borderColor|borderLeft|borderRight|borderTop|borderBottom|boxShadow|outline(?:Color)?)\s*:/;

// style={{ pattern
const INLINE_STYLE_OPEN = /style\s*=\s*\{\{/;

// Justification comment pattern (on same line or preceding line)
const JUSTIFICATION_COMMENT = /\/\/\s*Justification:/i;

// ============================================================================
// Scanner
// ============================================================================

function scanFile(filePath, componentName) {
  const absPath = resolve(projectRoot, filePath);
  if (!existsSync(absPath)) {
    return { file: filePath, component: componentName, errors: [`File not found: ${absPath}`], violations: [] };
  }

  const content = readFileSync(absPath, 'utf-8');
  const lines = content.split('\n');
  const violations = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lineNum = i + 1;

    // Skip comments and imports
    if (line.trimStart().startsWith('//') || line.trimStart().startsWith('*') || line.trimStart().startsWith('/*')) {
      continue;
    }

    // Skip JSDoc @param lines that mention hex as documentation
    if (line.includes('@param') || line.includes('@example')) {
      continue;
    }

    // Check hex literals
    const hexMatches = [...line.matchAll(HEX_LITERAL)];
    for (const match of hexMatches) {
      // Exclude CSS custom property references (var(--xxx))
      // Exclude CSS selectors in .css files (e.g., .dark .glass-tooltip)
      // Exclude hex in comments
      const beforeMatch = line.substring(0, match.index);
      if (beforeMatch.includes('var(--') || beforeMatch.trimStart().startsWith('//') || beforeMatch.trimStart().startsWith('*')) {
        continue;
      }
      violations.push({
        line: lineNum,
        category: 'HEX',
        snippet: line.trim().substring(0, 120),
        match: match[0],
      });
    }

    // Check Tailwind arbitrary hex classes
    const arbMatches = [...line.matchAll(ARB_HEX_CLASS)];
    for (const match of arbMatches) {
      violations.push({
        line: lineNum,
        category: 'ARB_HEX_CLASS',
        snippet: line.trim().substring(0, 120),
        match: match[0],
      });
    }
  }

  return { file: filePath, component: componentName, errors: [], violations };
}

function scanForInlineStyles(filePath, componentName) {
  const absPath = resolve(projectRoot, filePath);
  if (!existsSync(absPath) || !filePath.endsWith('.tsx')) return [];

  const content = readFileSync(absPath, 'utf-8');
  const lines = content.split('\n');
  const violations = [];

  let insideStyleBlock = false;
  let styleBlockStartLine = -1;
  let braceDepth = 0;
  let hasJustification = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lineNum = i + 1;

    // Check for justification comment on this line or previous line
    if (JUSTIFICATION_COMMENT.test(line)) {
      hasJustification = true;
      continue;
    }

    // Detect style={{ opening
    if (INLINE_STYLE_OPEN.test(line) && !insideStyleBlock) {
      insideStyleBlock = true;
      styleBlockStartLine = lineNum;
      braceDepth = 0;

      // Check if previous line has justification
      if (i > 0 && JUSTIFICATION_COMMENT.test(lines[i - 1])) {
        hasJustification = true;
      }

      // Count braces on this line
      for (const ch of line) {
        if (ch === '{') braceDepth++;
        if (ch === '}') braceDepth--;
      }

      // Check for theming keys on the opening line
      if (!hasJustification && THEMING_STYLE_KEYS.test(line)) {
        violations.push({
          line: lineNum,
          category: 'INLINE_STYLE',
          snippet: line.trim().substring(0, 120),
          component: componentName,
        });
      }

      if (braceDepth <= 0) {
        insideStyleBlock = false;
        hasJustification = false;
      }
      continue;
    }

    if (insideStyleBlock) {
      for (const ch of line) {
        if (ch === '{') braceDepth++;
        if (ch === '}') braceDepth--;
      }

      if (!hasJustification && THEMING_STYLE_KEYS.test(line)) {
        violations.push({
          line: lineNum,
          category: 'INLINE_STYLE',
          snippet: line.trim().substring(0, 120),
          component: componentName,
        });
      }

      if (braceDepth <= 0) {
        insideStyleBlock = false;
        hasJustification = false;
      }
    }
  }

  return violations;
}

// ============================================================================
// Find companion CSS files
// ============================================================================

function findCompanionCss(tsxPath) {
  const absPath = resolve(projectRoot, tsxPath);
  const content = readFileSync(absPath, 'utf-8');
  const cssImports = [...content.matchAll(/import\s+['"]\.\/([^'"]+\.css)['"]/g)];
  const dir = dirname(absPath);
  return cssImports.map(m => {
    const cssFile = join(dir, m[1]);
    // Convert back to relative path from projectRoot
    const relative = cssFile.replace(resolve(projectRoot) + '\\', '').replace(resolve(projectRoot) + '/', '');
    return relative.replace(/\\/g, '/');
  }).filter(p => existsSync(resolve(projectRoot, p)));
}

// ============================================================================
// Main
// ============================================================================

console.log('🔍 D2 Token Drift Sentinel Scanner');
console.log('='.repeat(80));
console.log();

let totalHexViolations = 0;
let totalArbHexViolations = 0;
let totalInlineStyleViolations = 0;
let allResults = [];

for (const comp of D2_COMPONENTS) {
  // Scan the TSX file
  const result = scanFile(comp.path, comp.name);

  // Find and scan companion CSS files
  const companionCss = findCompanionCss(comp.path);
  const cssResults = companionCss.map(cssPath => scanFile(cssPath, `${comp.name} (CSS)`));

  // Scan for inline style violations (TSX only)
  const inlineViolations = scanForInlineStyles(comp.path, comp.name);

  const allViolations = [
    ...result.violations,
    ...cssResults.flatMap(r => r.violations),
  ];

  const hexCount = allViolations.filter(v => v.category === 'HEX').length;
  const arbHexCount = allViolations.filter(v => v.category === 'ARB_HEX_CLASS').length;

  totalHexViolations += hexCount;
  totalArbHexViolations += arbHexCount;
  totalInlineStyleViolations += inlineViolations.length;

  allResults.push({
    component: comp.name,
    file: comp.path,
    companionCss,
    hexViolations: allViolations.filter(v => v.category === 'HEX'),
    arbHexViolations: allViolations.filter(v => v.category === 'ARB_HEX_CLASS'),
    inlineStyleViolations: inlineViolations,
    errors: [...result.errors, ...cssResults.flatMap(r => r.errors)],
  });
}

// ============================================================================
// Report
// ============================================================================

console.log('📋 D2-Authoritative Scope: %d components', D2_COMPONENTS.length);
console.log();

for (const result of allResults) {
  const total = result.hexViolations.length + result.arbHexViolations.length + result.inlineStyleViolations.length;
  const status = total === 0 ? '✅' : '❌';
  const cssNote = result.companionCss.length > 0 ? ` (+${result.companionCss.length} CSS)` : '';
  console.log(`${status} ${result.component}${cssNote}: ${total} violation(s)`);

  if (result.errors.length > 0) {
    for (const err of result.errors) {
      console.log(`   ⚠️  ${err}`);
    }
  }

  for (const v of result.hexViolations) {
    console.log(`   ❌ [HEX] Line ${v.line}: ${v.match} — ${v.snippet}`);
  }
  for (const v of result.arbHexViolations) {
    console.log(`   ❌ [ARB_HEX] Line ${v.line}: ${v.match} — ${v.snippet}`);
  }
  for (const v of result.inlineStyleViolations) {
    console.log(`   ❌ [INLINE_STYLE] Line ${v.line}: ${v.snippet}`);
  }
}

console.log();
console.log('━'.repeat(80));
console.log('Summary');
console.log('━'.repeat(80));
console.log(`  Hex literals:           ${totalHexViolations}`);
console.log(`  Arbitrary hex classes:  ${totalArbHexViolations}`);
console.log(`  Theming inline styles:  ${totalInlineStyleViolations}`);
console.log();

const totalViolations = totalHexViolations + totalArbHexViolations + totalInlineStyleViolations;

if (totalViolations === 0) {
  console.log('='.repeat(80));
  console.log('✅ D2 TOKEN DRIFT SCAN: PASS');
  console.log('='.repeat(80));
  console.log();
  console.log('Zero hex violations. Inline styles within allowlist.');
  process.exit(0);
} else {
  console.log('='.repeat(80));
  console.log('❌ D2 TOKEN DRIFT SCAN: FAIL');
  console.log('='.repeat(80));
  console.log();
  console.log(`${totalViolations} violation(s) found. Fix the issues above and re-run.`);
  process.exit(1);
}
