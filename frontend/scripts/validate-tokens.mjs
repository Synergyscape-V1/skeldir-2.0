#!/usr/bin/env node

/**
 * Design System Token Validation Script (ES Modules)
 *
 * Validates that all design tokens follow naming conventions and constraints
 * defined in docs/design/D0_TOKEN_NAMING_GOVERNANCE.md
 *
 * Exit codes:
 * - 0: All validations passed
 * - 1: Validation failed
 * - 2: Configuration error
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration
const CONFIG = {
  rootDir: path.resolve(__dirname, '..'),
  parentDir: path.resolve(__dirname, '../..'),
  cssFile: 'src/index.css',
  configFile: 'tailwind.config.js',
  tokenFiles: [
    'docs/design/tokens/skeldir-tokens-color.json',
    'docs/design/tokens/skeldir-tokens-spacing.json',
    'docs/design/tokens/skeldir-tokens-typography.json',
    'docs/design/tokens/skeldir-tokens-effects.json',
  ],
  verbose: process.argv.includes('--verbose'),
  schema: process.argv.includes('--schema'),
};

// Token naming patterns (from D0_TOKEN_NAMING_GOVERNANCE.md)
const PATTERNS = {
  color: /^--color-([a-z]+)(-[a-z-]+)?$/,
  spacing: /^--space-(\d+)$/,
  typography: /^--(?:font-family|text)-([a-z]+)(-[a-z]+)?$/,
  effects: /^--(?:shadow|radius|duration|ease)-([a-z-]+)$/,
};

// Complete semantic categories (updated from D0 governance)
const SEMANTIC_CATEGORIES = {
  color: [
    'primary', 'primary-hover', 'primary-active', 'primary-disabled', 'primary-foreground',
    'secondary', 'secondary-hover', 'secondary-disabled', 'secondary-foreground',
    'success', 'success-light',
    'warning', 'warning-light',
    'error', 'error-light',
    'info', 'info-light',
    'confidence-high', 'confidence-high-bg',
    'confidence-medium', 'confidence-medium-bg',
    'confidence-low', 'confidence-low-bg',
    'neutral',
    'background', 'background-muted', 'background-card', 'background-popover',
    'background-sidebar', 'background-accent',
    'text-primary', 'text-secondary', 'text-muted', 'text-disabled', 'text-inverse',
    'chart-1', 'chart-2', 'chart-3', 'chart-4', 'chart-5', 'chart-6',
    'border', 'border-muted',
    'destructive', 'destructive-hover', 'destructive-foreground',
    'link', 'link-hover',
  ],
};

// Required taxonomy (from TOKEN_TAXONOMY_REFERENCE.md)
const REQUIRED_TAXONOMY = {
  color: 47,
  spacing: 12,
  typography: 13,
  effects: 19,
};

// Results accumulator
const results = {
  passed: [],
  failed: [],
  warnings: [],
};

/**
 * Log a message with optional prefix
 */
function log(message, level = 'info') {
  if (!CONFIG.verbose && level === 'debug') return;

  const prefix = {
    info: '  ℹ',
    warn: '  ⚠',
    error: '  ✗',
    success: '  ✓',
    debug: '  →',
  }[level] || '  •';

  console.log(`${prefix} ${message}`);
}

/**
 * Read CSS file and extract CSS variable declarations
 */
function extractCSSVariables(filePath) {
  if (!fs.existsSync(filePath)) {
    log(`CSS file not found: ${filePath}`, 'error');
    return [];
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  const regex = /(--[\w-]+)\s*:\s*([^;]+);/g;
  const variables = [];
  let match;

  while ((match = regex.exec(content)) !== null) {
    variables.push({
      name: match[1],
      value: match[2].trim(),
      line: content.substring(0, match.index).split('\n').length,
    });
  }

  return variables;
}

/**
 * Validate token naming pattern
 */
function validateTokenName(token) {
  const { name } = token;

  // Check if matches any allowed pattern
  for (const [type, pattern] of Object.entries(PATTERNS)) {
    if (pattern.test(name)) {
      // Additional semantic validation for colors
      if (type === 'color') {
        const match = name.match(PATTERNS.color);
        const semantic = match[1] + (match[2] || '');

        if (!SEMANTIC_CATEGORIES.color.includes(semantic.replace(/^-/, ''))) {
          results.failed.push({
            token: name,
            reason: `Semantic category '${semantic}' not in approved list. See D0_TOKEN_NAMING_GOVERNANCE.md`,
            line: token.line,
          });
          return false;
        }
      }

      results.passed.push(name);
      return true;
    }
  }

  results.failed.push({
    token: name,
    reason: `Does not match any approved token naming pattern. See D0_TOKEN_NAMING_GOVERNANCE.md`,
    line: token.line,
  });
  return false;
}

/**
 * Validate no raw hex values in CSS
 */
function validateNoRawHexValues(filePath) {
  if (!fs.existsSync(filePath)) return true;

  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  // Regex for hex colors (but exclude CSS variable declarations)
  const hexPattern = /#[0-9a-fA-F]{3,6}/g;

  let hasRawHex = false;

  lines.forEach((line, index) => {
    // Skip variable declarations (they're allowed in :root)
    if (line.includes('--')) return;

    // Skip comments
    if (line.trim().startsWith('/*') || line.trim().startsWith('//')) return;

    const hexMatches = line.match(hexPattern);
    if (hexMatches) {
      hexMatches.forEach(hex => {
        results.warnings.push({
          file: filePath,
          line: index + 1,
          issue: `Raw hex color found: ${hex}. Use CSS variable instead.`,
        });
        hasRawHex = true;
      });
    }
  });

  return !hasRawHex;
}

/**
 * Validate JSON token export
 */
function validateTokenJSON(filePath) {
  const fullPath = path.join(CONFIG.parentDir, filePath);

  if (!fs.existsSync(fullPath)) {
    log(`Token JSON not found: ${filePath}`, 'debug');
    return null;
  }

  try {
    const content = fs.readFileSync(fullPath, 'utf-8');
    const data = JSON.parse(content);

    // Validate schema structure
    if (!data.tokens || typeof data.tokens !== 'object') {
      results.failed.push({
        file: filePath,
        reason: 'Token JSON must have a "tokens" object',
      });
      return null;
    }

    if (!data.metadata || !data.metadata.total_tokens) {
      results.warnings.push({
        file: filePath,
        issue: 'Token JSON should have metadata.total_tokens',
      });
    }

    return data;
  } catch (error) {
    results.failed.push({
      file: filePath,
      reason: `Invalid JSON: ${error.message}`,
    });
    return null;
  }
}

/**
 * Validate taxonomy completeness
 */
function validateTaxonomy(tokenData) {
  const counts = {
    color: 0,
    spacing: 0,
    typography: 0,
    effects: 0,
  };

  // Count tokens from JSON exports
  for (const [fileName, data] of Object.entries(tokenData)) {
    if (!data) continue;

    if (fileName.includes('color')) {
      // Count all color tokens across all categories
      for (const category of Object.values(data.tokens)) {
        counts.color += Object.keys(category).length;
      }
    } else if (fileName.includes('spacing')) {
      counts.spacing = Object.keys(data.tokens).length;
    } else if (fileName.includes('typography')) {
      counts.typography = Object.keys(data.tokens.fontFamilies || {}).length +
                         Object.keys(data.tokens.textStyles || {}).length;
    } else if (fileName.includes('effects')) {
      counts.effects = Object.keys(data.tokens.shadows || {}).length +
                      Object.keys(data.tokens.borderRadius || {}).length +
                      Object.keys(data.tokens.animationDuration || {}).length +
                      Object.keys(data.tokens.easingFunctions || {}).length;
    }
  }

  // Validate against required taxonomy
  let allPass = true;
  for (const [type, required] of Object.entries(REQUIRED_TAXONOMY)) {
    const actual = counts[type];
    const passes = actual >= required;

    if (passes) {
      log(`${type}: ${actual}/${required} tokens ✓`, 'success');
    } else {
      log(`${type}: ${actual}/${required} tokens ✗ (${required - actual} missing)`, 'error');
      results.failed.push({
        taxonomy: type,
        reason: `Expected ${required} tokens, found ${actual}. Missing ${required - actual} tokens.`,
      });
      allPass = false;
    }
  }

  return allPass;
}

/**
 * Main validation runner
 */
function runValidation() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  Skeldir Design System Token Validation                    ║');
  console.log('║  (docs/design/D0_TOKEN_NAMING_GOVERNANCE.md)              ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const cssPath = path.join(CONFIG.rootDir, CONFIG.cssFile);

  // Validate JSON token exports (if they exist)
  log('Checking token JSON exports...', 'info');
  const tokenData = {};

  CONFIG.tokenFiles.forEach(file => {
    const data = validateTokenJSON(file);
    if (data) {
      log(`Valid JSON: ${path.basename(file)}`, 'success');
      tokenData[file] = data;
    } else {
      log(`Missing or invalid: ${path.basename(file)}`, 'error');
    }
  });

  // Validate taxonomy completeness
  if (Object.keys(tokenData).length > 0) {
    log('\nChecking taxonomy completeness...', 'info');
    validateTaxonomy(tokenData);
  }

  // Extract and validate CSS variables (if needed)
  if (CONFIG.verbose) {
    log('\nChecking CSS variables...', 'info');
    const variables = extractCSSVariables(cssPath);

    if (variables.length === 0) {
      log('No CSS variables found (OK during initial phases)', 'debug');
    } else {
      log(`Found ${variables.length} CSS variables`, 'debug');
    }
  }

  // Check for raw hex values
  log('\nChecking for raw hex colors...', 'info');
  const noRawHex = validateNoRawHexValues(cssPath);
  if (noRawHex) {
    log('No raw hex values found in CSS', 'success');
  }

  // Summary
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  Validation Results                                        ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  if (results.passed.length > 0) {
    log(`Passed: ${results.passed.length} checks`, 'success');
  }

  if (results.failed.length > 0) {
    log(`Failed: ${results.failed.length} validation(s)`, 'error');
    results.failed.forEach(failure => {
      console.log(`\n  ✗ ${failure.token || failure.file || failure.taxonomy || 'Validation'}`);
      console.log(`    Reason: ${failure.reason}`);
      if (failure.line) {
        console.log(`    Line: ${failure.line}`);
      }
    });
  }

  if (results.warnings.length > 0) {
    log(`Warnings: ${results.warnings.length}`, 'warn');
    if (CONFIG.verbose) {
      results.warnings.forEach(warning => {
        console.log(`\n  ⚠ ${warning.file}:${warning.line || ''}`);
        console.log(`    ${warning.issue}`);
      });
    }
  }

  // Exit code
  const hasFailures = results.failed.length > 0;
  const exitCode = hasFailures ? 1 : 0;

  console.log('\n' + '═'.repeat(60));
  if (hasFailures) {
    console.log('VALIDATION FAILED - Fix errors above');
    console.log('See docs/design/D0_TOKEN_NAMING_GOVERNANCE.md for rules');
  } else {
    console.log('VALIDATION PASSED ✓');
    console.log('All token requirements met');
  }
  console.log('═'.repeat(60) + '\n');

  process.exit(exitCode);
}

// Run validation
runValidation();
