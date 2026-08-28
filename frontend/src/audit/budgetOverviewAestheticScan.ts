import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');
const BUDGET_COMPONENT_DIR = join(ROOT, 'src', 'components', 'budget');
const BUDGET_COPY = join(ROOT, 'src', 'budget', 'copy.ts');
const BUDGET_HEADER = join(
  BUDGET_COMPONENT_DIR,
  'BudgetSimulationPageHeader',
  'BudgetSimulationPageHeader.tsx',
);
const BUDGET_PANEL = join(BUDGET_COMPONENT_DIR, 'budgetPanel.module.css');
const BUDGET_INPUT_PAGE_CSS = join(
  BUDGET_COMPONENT_DIR,
  'BudgetInputPage',
  'BudgetInputPage.module.css',
);
const BUDGET_INPUT_CARD_CSS = join(
  BUDGET_COMPONENT_DIR,
  'BudgetSimulationInputCard',
  'BudgetSimulationInputCard.module.css',
);
const BUDGET_RIGHT_COLUMN_CSS = join(
  BUDGET_COMPONENT_DIR,
  'BudgetSimulationRightColumn',
  'BudgetSimulationRightColumn.module.css',
);

export interface AestheticViolation {
  file: string;
  rule: string;
  detail: string;
}

function walkCss(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walkCss(full, acc);
    else if (entry.endsWith('.module.css')) acc.push(full);
  }
  return acc;
}

/** Framework D commercial-polish scan scoped to Budget Simulation surfaces. */
export function scanBudgetOverviewAesthetic(sourceOverride?: {
  cssFiles?: Record<string, string>;
  headerTsx?: string;
  copyTs?: string;
  panelCss?: string;
  inputPageCss?: string;
  inputCardCss?: string;
  rightColumnCss?: string;
}): AestheticViolation[] {
  const violations: AestheticViolation[] = [];

  const cssFiles =
    sourceOverride?.cssFiles ??
    Object.fromEntries(walkCss(BUDGET_COMPONENT_DIR).map((f) => [relative(ROOT, f), readFileSync(f, 'utf8')]));

  for (const [file, content] of Object.entries(cssFiles)) {
    if (/linear-gradient|radial-gradient/i.test(content)) {
      violations.push({ file, rule: 'D-no-gradient', detail: 'Gradient aesthetic detected' });
    }
    if (/border-left:\s*[^;]*solid/i.test(content) && /border-left:\s*[234]px/i.test(content)) {
      violations.push({ file, rule: 'D-no-side-border-card', detail: 'Accent side-border card pattern' });
    }
    if (/border-radius:\s*0(?:px)?;/i.test(content)) {
      violations.push({ file, rule: 'D-radius-hierarchy', detail: 'Zero border-radius breaks Overview chip/surface hierarchy' });
    }
    if (/box-shadow:\s*[^;]*rgba\(/i.test(content)) {
      violations.push({
        file,
        rule: 'D-no-hardcoded-rgba-shadow',
        detail: 'Hardcoded rgba box-shadow — use token elevation or none (Overview border-first)',
      });
    }
    if (/glow|drop-shadow\(/i.test(content)) {
      violations.push({ file, rule: 'D-no-glow', detail: 'Glow / drop-shadow decoration detected' });
    }
  }

  const panelCss = sourceOverride?.panelCss ?? readFileSync(BUDGET_PANEL, 'utf8');
  if (/elevatedPanel:hover/i.test(panelCss) && /box-shadow/i.test(panelCss.match(/elevatedPanel:hover[\s\S]*?\}/)?.[0] ?? '')) {
    violations.push({
      file: relative(ROOT, BUDGET_PANEL),
      rule: 'D-no-static-panel-hover-lift',
      detail: 'Static panel hover elevation lift diverges from Overview DNA',
    });
  }
  if (/box-shadow:\s*var\(--sk-elevation-card\)/.test(panelCss)) {
    violations.push({
      file: relative(ROOT, BUDGET_PANEL),
      rule: 'D-overview-border-first',
      detail: 'Elevated panel still uses card elevation; Overview summary tiles are border-first',
    });
  }

  const inputPageCss = sourceOverride?.inputPageCss ?? readFileSync(BUDGET_INPUT_PAGE_CSS, 'utf8');
  if (/--sk-elevation-budget-panel/.test(inputPageCss)) {
    violations.push({
      file: relative(ROOT, BUDGET_INPUT_PAGE_CSS),
      rule: 'D-no-parallel-elevation-system',
      detail: 'Budget-local elevation custom property remains',
    });
  }
  if (!/gap:\s*var\(--spacing-24\)/.test(inputPageCss)) {
    violations.push({
      file: relative(ROOT, BUDGET_INPUT_PAGE_CSS),
      rule: 'D-page-rhythm',
      detail: 'Page vertical rhythm must use Overview --spacing-24',
    });
  }

  const inputCardCss = sourceOverride?.inputCardCss ?? readFileSync(BUDGET_INPUT_CARD_CSS, 'utf8');
  if (/border-radius:\s*0/.test(inputCardCss)) {
    violations.push({
      file: relative(ROOT, BUDGET_INPUT_CARD_CSS),
      rule: 'D-chip-radius',
      detail: 'Input chip radius is 0',
    });
  }

  const rightColumnCss = sourceOverride?.rightColumnCss ?? readFileSync(BUDGET_RIGHT_COLUMN_CSS, 'utf8');
  if (/rgba\(15,\s*23,\s*42/.test(rightColumnCss)) {
    violations.push({
      file: relative(ROOT, BUDGET_RIGHT_COLUMN_CSS),
      rule: 'D-cta-shadow-theater',
      detail: 'Submit CTA still uses hardcoded slate rgba shadows',
    });
  }
  if (/translateY\(-1px\)/.test(rightColumnCss)) {
    violations.push({
      file: relative(ROOT, BUDGET_RIGHT_COLUMN_CSS),
      rule: 'D-cta-hover-lift',
      detail: 'Submit CTA hover lift diverges from Overview primaryAction DNA',
    });
  }

  const headerTsx = sourceOverride?.headerTsx ?? readFileSync(BUDGET_HEADER, 'utf8');
  if (!/pageHeaderStack/.test(headerTsx) || !/data-budget-header-row/.test(headerTsx)) {
    violations.push({
      file: relative(ROOT, BUDGET_HEADER),
      rule: 'D-header-grammar',
      detail: 'Header must compose Overview reflowLayout pageHeaderRow/stack grammar',
    });
  }
  if (!/metadataLine/.test(headerTsx)) {
    violations.push({
      file: relative(ROOT, BUDGET_HEADER),
      rule: 'D-header-metadata',
      detail: 'Missing Overview-parity metadata line',
    });
  }

  const copyTs = sourceOverride?.copyTs ?? readFileSync(BUDGET_COPY, 'utf8');
  if (!/metadataLine:/.test(copyTs)) {
    violations.push({
      file: relative(ROOT, BUDGET_COPY),
      rule: 'D-copy-metadata',
      detail: 'BUDGET_SIMULATION_COPY.metadataLine missing',
    });
  }

  return violations;
}

/** Deliberate sabotage fixture proving the harness is non-vacuous. */
export function commercialPolishSabotageFixture(): string {
  return `
.elevatedPanel:hover {
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
}
.chip { border-radius: 0; }
.card { background: linear-gradient(90deg, #7c3aed, #4f46e5); border-left: 3px solid #7c3aed; }
`;
}
