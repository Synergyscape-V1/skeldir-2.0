#!/usr/bin/env node

/**
 * Design System Token Validation Script
 *
 * Validates that all design tokens follow naming conventions and constraints
 * defined in docs/design/D0_TOKEN_NAMING_GOVERNANCE.md
 *
 * Exit codes:
 * - 0: All validations passed
 * - 1: Validation failed
 * - 2: Configuration error
 */

const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  rootDir: path.resolve(__dirname, '..'),
  cssFile: 'src/index.css',
  configFile: 'tailwind.config.js',
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

// Semantic categories that are allowed
const SEMANTIC_CATEGORIES = {
  color: [
    'primary',
    'success',
    'warning',
    'error',
    'info',
    'confidence-high',
    'confidence-medium',
    'confidence-low',
    'neutral',
    'background',
    'text',
    'border',
  ],
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
        const semantic = match[1];

        if (!SEMANTIC_CATEGORIES.color.includes(semantic)) {
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
 * Validate spacing values (should use var(--space-*))
 */
function validateNoRawSpacing(filePath) {
  if (!fs.existsSync(filePath)) return true;

  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  // Regex for raw pixel values in common spacing properties
  const spacingPattern = /(?:padding|margin|gap|width|height)\s*:\s*(?!var)\d+px/g;

  let hasRawSpacing = false;

  lines.forEach((line, index) => {
    if (line.includes('var(--')) return; // Skip if already using variables

    const matches = line.match(spacingPattern);
    if (matches) {
      matches.forEach(match => {
        results.warnings.push({
          file: filePath,
          line: index + 1,
          issue: `Raw pixel spacing found: ${match}. Use CSS variable instead.`,
        });
        hasRawSpacing = true;
      });
    }
  });

  return !hasRawSpacing;
}

/**
 * Validate JSON schema for token exports
 */
function validateTokenJSON(filePath) {
  if (!fs.existsSync(filePath)) {
    log(`Token JSON not found: ${filePath}`, 'debug');
    return null;
  }

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const tokens = JSON.parse(content);

    // Basic schema validation
    if (!tokens || typeof tokens !== 'object') {
      results.failed.push({
        file: filePath,
        reason: 'Token JSON must be an object',
      });
      return null;
    }

    return tokens;
  } catch (error) {
    results.failed.push({
      file: filePath,
      reason: `Invalid JSON: ${error.message}`,
    });
    return null;
  }
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

  // Extract and validate CSS variables
  log('Checking CSS variables...', 'info');
  const variables = extractCSSVariables(cssPath);

  if (variables.length === 0) {
    log('No CSS variables found (OK during initial phases)', 'debug');
  } else {
    log(`Found ${variables.length} CSS variables`, 'debug');
    variables.forEach(token => {
      validateTokenName(token);
    });
  }

  // Check for raw hex values
  log('Checking for raw hex colors...', 'info');
  const noRawHex = validateNoRawHexValues(cssPath);
  if (noRawHex) {
    log('No raw hex values found', 'success');
  }

  // Check for raw spacing
  log('Checking for raw spacing values...', 'info');
  const noRawSpacing = validateNoRawSpacing(cssPath);
  if (noRawSpacing) {
    log('No raw spacing values found', 'success');
  }

  // Validate JSON token exports (if they exist)
  if (CONFIG.schema) {
    log('Checking token JSON schema...', 'info');
    const tokenFiles = [
      'docs/design/tokens/skeldir-tokens-color.json',
      'docs/design/tokens/skeldir-tokens-spacing.json',
      'docs/design/tokens/skeldir-tokens-typography.json',
      'docs/design/tokens/skeldir-tokens-effects.json',
    ];

    tokenFiles.forEach(file => {
      const fullPath = path.join(CONFIG.rootDir, '..', file);
      const tokens = validateTokenJSON(fullPath);
      if (tokens) {
        log(`Valid JSON: ${file}`, 'success');
      }
    });
  }

  // Summary
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  Validation Results                                        ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  if (results.passed.length > 0) {
    log(`Passed: ${results.passed.length} tokens`, 'success');
  }

  if (results.failed.length > 0) {
    log(`Failed: ${results.failed.length} validation(s)`, 'error');
    results.failed.forEach(failure => {
      console.log(`\n  ✗ ${failure.token || failure.file}`);
      console.log(`    Reason: ${failure.reason}`);
      if (failure.line) {
        console.log(`    Line: ${failure.line}`);
      }
    });
  }

  if (results.warnings.length > 0) {
    log(`Warnings: ${results.warnings.length}`, 'warn');
    results.warnings.forEach(warning => {
      console.log(`\n  ⚠ ${warning.file}:${warning.line}`);
      console.log(`    ${warning.issue}`);
    });
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
  }
  console.log('═'.repeat(60) + '\n');

  process.exit(exitCode);
}

// Run validation
runValidation();
