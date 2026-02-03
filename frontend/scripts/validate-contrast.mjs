#!/usr/bin/env node

/**
 * WCAG AA Contrast Validation for Design Tokens
 *
 * Validates color token pairs meet WCAG AA contrast requirements:
 * - Body text: 4.5:1 minimum
 * - Large text (18pt+ or 14pt bold+): 3:1 minimum
 * - Interactive elements: 3:1 minimum
 *
 * Exit codes:
 * - 0: All pairs pass WCAG AA
 * - 1: One or more pairs fail
 */

/**
 * Convert HSL to RGB
 */
function hslToRgb(h, s, l) {
  s /= 100;
  l /= 100;

  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = l - c / 2;

  let r, g, b;
  if (h >= 0 && h < 60) {
    [r, g, b] = [c, x, 0];
  } else if (h >= 60 && h < 120) {
    [r, g, b] = [x, c, 0];
  } else if (h >= 120 && h < 180) {
    [r, g, b] = [0, c, x];
  } else if (h >= 180 && h < 240) {
    [r, g, b] = [0, x, c];
  } else if (h >= 240 && h < 300) {
    [r, g, b] = [x, 0, c];
  } else {
    [r, g, b] = [c, 0, x];
  }

  return [
    Math.round((r + m) * 255),
    Math.round((g + m) * 255),
    Math.round((b + m) * 255)
  ];
}

/**
 * Calculate relative luminance
 */
function getLuminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map(c => {
    c = c / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Calculate contrast ratio between two colors
 */
function getContrastRatio(rgb1, rgb2) {
  const lum1 = getLuminance(...rgb1);
  const lum2 = getLuminance(...rgb2);
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Validate a color pair
 */
function validatePair(name, fg, bg, requirement) {
  const fgRgb = hslToRgb(...fg);
  const bgRgb = hslToRgb(...bg);
  const ratio = getContrastRatio(fgRgb, bgRgb);
  const passes = ratio >= requirement;

  return {
    name,
    fg,
    bg,
    ratio: ratio.toFixed(2),
    requirement,
    passes
  };
}

/**
 * Main validation
 */
function runContrastValidation() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  WCAG AA Contrast Validation                              ║');
  console.log('║  Minimum contrast ratios for token pairs                  ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const results = [];

  // Define token pairs to validate (using HSL from current system as reference)
  // These are placeholder values - will be replaced when canonical tokens are defined

  // Body text pairs (4.5:1 requirement)
  results.push(validatePair(
    'Primary text on background',
    [215, 25, 15],  // --foreground in light mode
    [0, 0, 100],    // --background in light mode
    4.5
  ));

  results.push(validatePair(
    'Muted text on background',
    [215, 15, 45],  // --muted-foreground
    [0, 0, 100],    // --background
    4.5
  ));

  // Status text pairs (4.5:1 requirement)
  results.push(validatePair(
    'Success text on light background',
    [160, 84, 25],  // --verified-foreground (dark)
    [0, 0, 100],    // --background
    4.5
  ));

  results.push(validatePair(
    'Warning text on light background',
    [38, 92, 35],   // --unverified-foreground (dark)
    [0, 0, 100],    // --background
    4.5
  ));

  // Interactive element pairs (3:1 requirement)
  results.push(validatePair(
    'Primary button text on primary bg',
    [0, 0, 100],    // --primary-foreground (white)
    [217, 91, 42],  // --primary (navy)
    3.0
  ));

  results.push(validatePair(
    'Destructive button text on destructive bg',
    [0, 15, 98],    // --destructive-foreground
    [0, 84, 60],    // --destructive
    3.0
  ));

  // Display results
  console.log('Body Text Pairs (4.5:1 minimum):');
  console.log('━'.repeat(60));

  const bodyPairs = results.filter(r => r.requirement === 4.5);
  bodyPairs.forEach(result => {
    const status = result.passes ? '✓ PASS' : '✗ FAIL';
    const icon = result.passes ? '✓' : '✗';
    console.log(`  ${icon} ${result.name}`);
    console.log(`    Ratio: ${result.ratio}:1 (${result.passes ? 'passes' : 'fails'} ${result.requirement}:1)`);
  });

  console.log('\nInteractive Element Pairs (3:1 minimum):');
  console.log('━'.repeat(60));

  const interactivePairs = results.filter(r => r.requirement === 3.0);
  interactivePairs.forEach(result => {
    const icon = result.passes ? '✓' : '✗';
    console.log(`  ${icon} ${result.name}`);
    console.log(`    Ratio: ${result.ratio}:1 (${result.passes ? 'passes' : 'fails'} ${result.requirement}:1)`);
  });

  // Summary
  const totalPairs = results.length;
  const passing = results.filter(r => r.passes).length;
  const failing = totalPairs - passing;

  console.log('\n' + '═'.repeat(60));
  console.log(`Total Pairs: ${totalPairs}`);
  console.log(`Passing: ${passing}`);
  console.log(`Failing: ${failing}`);

  if (failing > 0) {
    console.log('\n⚠ CONTRAST VALIDATION FAILED');
    console.log('Some color pairs do not meet WCAG AA requirements.');
    console.log('Fix contrast ratios before proceeding with D0-P1 completion.');
  } else {
    console.log('\n✓ CONTRAST VALIDATION PASSED');
    console.log('All color pairs meet WCAG AA requirements.');
  }
  console.log('═'.repeat(60) + '\n');

  process.exit(failing > 0 ? 1 : 0);
}

// Run validation
runContrastValidation();
