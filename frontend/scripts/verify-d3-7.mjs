#!/usr/bin/env node
/**
 * D3.7 §8 — Non-Vacuous Proof Verifier
 *
 * Enforces the D3.7 integration baseline invariants. Must FAIL when
 * any invariant is broken and PASS when all are intact.
 *
 * Minimum checks:
 *   1. Required shadcn primitive files exist (exact set, not count)
 *   2. @tremor/react resolves to 3.x.x
 *   3. index.css contains all required shadcn variable names AND they are
 *      bare HSL channels (not wrapped in hsl())
 *   4. tailwind.config.js contains the Tremor theme keys with correct targets
 *   5. Canonical table component and its Storybook story exist
 *   6. Icon guide exists at exact path
 *
 * Usage:
 *   node scripts/verify-d3-7.mjs
 *
 * Cursor workflow:
 *   Run after any D3.7 file change. Exit code 0 = pass, 1 = fail.
 *   Non-vacuity demo: rename a required UI file, run verifier (expect fail),
 *   restore, run verifier (expect pass).
 */

import { readFileSync, existsSync } from 'node:fs'
import { execSync } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')

let failures = 0
let passes = 0

function check(label, condition) {
  if (condition) {
    console.log(`  PASS  ${label}`)
    passes++
  } else {
    console.error(`  FAIL  ${label}`)
    failures++
  }
}

console.log('D3.7 Integration Baseline Verifier')
console.log('===================================\n')

/* ------------------------------------------------------------------ */
/*  1. Required shadcn primitive files (exact set)                     */
/* ------------------------------------------------------------------ */
console.log('[1] shadcn primitive inventory')

const REQUIRED_PRIMITIVES = [
  'button', 'input', 'card', 'dialog', 'select', 'form', 'table',
  'tabs', 'accordion', 'alert', 'badge', 'progress', 'skeleton',
  'tooltip', 'avatar', 'checkbox', 'radio-group', 'switch',
]

for (const prim of REQUIRED_PRIMITIVES) {
  const filePath = resolve(ROOT, 'src', 'components', 'ui', `${prim}.tsx`)
  check(`ui/${prim}.tsx exists`, existsSync(filePath))
}

/* ------------------------------------------------------------------ */
/*  2. @tremor/react resolves to 3.x.x                                */
/* ------------------------------------------------------------------ */
console.log('\n[2] Tremor version')

try {
  const tremorVersion = execSync('npm list @tremor/react --json', {
    cwd: ROOT,
    encoding: 'utf-8',
  })
  const parsed = JSON.parse(tremorVersion)
  // Navigate the npm list JSON structure
  const version = parsed?.dependencies?.['@tremor/react']?.version || ''
  check(`@tremor/react is 3.x.x (got ${version})`, /^3\.\d+\.\d+/.test(version))
} catch {
  check('@tremor/react is installed', false)
}

/* ------------------------------------------------------------------ */
/*  3. index.css contains required shadcn variables as HSL channels    */
/* ------------------------------------------------------------------ */
console.log('\n[3] index.css token mapping')

const indexCss = readFileSync(resolve(ROOT, 'src', 'index.css'), 'utf-8')

const REQUIRED_CSS_VARS = [
  '--background', '--foreground', '--primary', '--primary-foreground',
  '--secondary', '--muted', '--accent', '--destructive',
  '--border', '--input', '--ring',
]

for (const varName of REQUIRED_CSS_VARS) {
  // Check that the variable appears in a :root or .dark block with HSL channel value
  // Pattern: variable name followed by colon, then HSL channel values (digits, spaces, %)
  const pattern = new RegExp(`${varName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:\\s*\\d`)
  check(`${varName} defined with HSL channels`, pattern.test(indexCss))
}

// Check that the stale @layer base duplicate has been removed
const hasStaleLayerBase = /@layer base\s*\{[^}]*--primary:\s*222\.2\s+47\.4%/s.test(indexCss)
check('Stale @layer base shadcn defaults removed', !hasStaleLayerBase)

/* ------------------------------------------------------------------ */
/*  4. tailwind.config.js contains Tremor theme keys                   */
/* ------------------------------------------------------------------ */
console.log('\n[4] Tailwind Tremor theme keys')

const tailwindConfig = readFileSync(resolve(ROOT, 'tailwind.config.js'), 'utf-8')

const TREMOR_KEYS = [
  { key: 'tremor-brand', target: '--primary' },
  { key: 'tremor-background', target: '--background' },
  { key: 'tremor-content', target: '--foreground' },
  { key: 'tremor-ring', target: '--primary' },
]

for (const { key, target } of TREMOR_KEYS) {
  check(
    `${key} → ${target}`,
    tailwindConfig.includes(`'${key}'`) && tailwindConfig.includes(`var(${target})`)
  )
}

/* ------------------------------------------------------------------ */
/*  5. Canonical table component and Storybook story exist             */
/* ------------------------------------------------------------------ */
console.log('\n[5] Integration deliverables')

check(
  'CanonicalDataTable.tsx exists',
  existsSync(resolve(ROOT, 'src', 'components', 'tables', 'CanonicalDataTable.tsx'))
)
check(
  'canonical-data-table.stories.tsx exists',
  existsSync(resolve(ROOT, 'src', 'stories', 'canonical-data-table.stories.tsx'))
)
check(
  'shadcn-theme.stories.tsx exists',
  existsSync(resolve(ROOT, 'src', 'stories', 'shadcn-theme.stories.tsx'))
)
check(
  'tremor-theme.stories.tsx exists',
  existsSync(resolve(ROOT, 'src', 'stories', 'tremor-theme.stories.tsx'))
)

/* ------------------------------------------------------------------ */
/*  6. Icon guide exists at exact path                                 */
/* ------------------------------------------------------------------ */
console.log('\n[6] Icon usage guide')

check(
  'src/components/icons/README.md exists',
  existsSync(resolve(ROOT, 'src', 'components', 'icons', 'README.md'))
)

/* ------------------------------------------------------------------ */
/*  Summary                                                            */
/* ------------------------------------------------------------------ */
console.log('\n===================================')
console.log(`Results: ${passes} passed, ${failures} failed`)

if (failures > 0) {
  console.error('\nD3.7 VERIFICATION FAILED')
  process.exit(1)
} else {
  console.log('\nD3.7 VERIFICATION PASSED')
  process.exit(0)
}
