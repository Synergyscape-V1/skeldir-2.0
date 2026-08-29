import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

export interface DensityAuditViolation {
  check: string;
  expected: string;
  actual?: string;
}

const COMPACT_ASSERTIONS: Array<{ check: string; pattern: RegExp }> = [
  { check: 'compact-body-font', pattern: /--sk-font-size-body:\s*13px/ },
  { check: 'compact-h1', pattern: /--sk-font-size-h1:\s*24px/ },
  { check: 'compact-h2', pattern: /--sk-font-size-h2:\s*20px/ },
  { check: 'compact-page-gap', pattern: /--sk-space-6:\s*16px/ },
  { check: 'compact-table-row-standard', pattern: /--sk-dimension-table-row-standard:\s*44px/ },
  { check: 'compact-table-row-dense', pattern: /--sk-dimension-table-row-dense:\s*40px/ },
  { check: 'compact-header-height', pattern: /--sk-dimension-header-height:\s*42px/ },
  { check: 'compact-nav-item', pattern: /--sk-dimension-nav-item-height:\s*34px/ },
  { check: 'compact-table-cell-block', pattern: /--sk-dimension-table-cell-padding-block:\s*var\(--sk-space-2\)/ },
  { check: 'compact-supervisory-row', pattern: /--sk-dimension-command-center-supervisory-row-min-height:\s*360px/ },
];

const WIRING_ASSERTIONS: Array<{ check: string; pattern: RegExp; file: string }> = [
  {
    check: 'shell-density-attribute',
    file: 'src/components/shell/AuthenticatedAppShell/AuthenticatedAppShell.tsx',
    pattern: /data-density=\{density\}/,
  },
  {
    check: 'density-styles-imported',
    file: 'src/main.tsx',
    pattern: /density\.css/,
  },
  {
    check: 'table-cell-padding-token',
    file: 'src/components/layout/Table/Table.module.css',
    pattern: /--sk-dimension-table-cell-padding-block/,
  },
  {
    check: 'spacing-20-alias',
    file: 'src/tokens/tokens.css',
    pattern: /--spacing-20:\s*var\(--sk-space-5\)/,
  },
];

export function runDensityTokenAudit() {
  const densityCss = readFileSync(join(ROOT, 'src', 'tokens', 'density.css'), 'utf8');
  const rootCss = readFileSync(join(ROOT, 'src', 'tokens', 'tokens.css'), 'utf8');
  const violations: DensityAuditViolation[] = [];

  for (const { check, pattern } of COMPACT_ASSERTIONS) {
    if (!pattern.test(densityCss)) {
      violations.push({ check, expected: pattern.source });
    }
  }

  for (const { check, pattern, file } of WIRING_ASSERTIONS) {
    const content = readFileSync(join(ROOT, file), 'utf8');
    if (!pattern.test(content)) {
      violations.push({ check, expected: pattern.source, actual: file });
    }
  }

  if (!/--sk-dimension-table-row-standard:\s*64px/.test(rootCss)) {
    violations.push({
      check: 'comfortable-baseline-row',
      expected: 'comfortable 64px row baseline on :root',
    });
  }

  if (/--sk-dimension-table-row-standard:\s*64px/.test(densityCss)) {
    violations.push({
      check: 'compact-must-not-inherit-64px-row',
      expected: 'compact profile must override 64px rows',
    });
  }

  for (const file of [
    'src/components/trust/AuthorityBadge/AuthorityBadge.module.css',
    'src/components/trust/PolicyAuthorityPill/PolicyAuthorityPill.module.css',
  ]) {
    const content = readFileSync(join(ROOT, file), 'utf8');
    if (/\.\w+\.\w+[\s\S]*?composes:/.test(content)) {
      violations.push({
        check: 'no-compound-selector-composes',
        expected: 'CSS modules composes only on single :local class names',
        actual: file,
      });
    }
  }

  return { violations, checksRun: COMPACT_ASSERTIONS.length + WIRING_ASSERTIONS.length + 4 };
}

export function compactDensityReductionRatio(): {
  comfortableRowPx: number;
  compactRowPx: number;
  verticalReductionPercent: number;
} {
  const comfortableRowPx = 64;
  const compactRowPx = 44;
  const verticalReductionPercent = ((comfortableRowPx - compactRowPx) / comfortableRowPx) * 100;
  return { comfortableRowPx, compactRowPx, verticalReductionPercent };
}
