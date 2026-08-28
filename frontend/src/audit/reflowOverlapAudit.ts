import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const SUBSTRATE_FILE = 'src/styles/reflowLayout.module.css';

const PAGE_HEADER_FILES = [
  'src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.module.css',
  'src/components/claims/ClaimsLedgerPage/ClaimsLedgerPage.module.css',
  'src/components/channels/ChannelsOverviewPage/ChannelsOverviewPage.module.css',
  'src/components/trustIndex/TrustEnvelopeIndexPage/TrustEnvelopeIndexPage.module.css',
  'src/components/trust/TrustEnvelopeOperatorView/TrustEnvelopeDetailPage.module.css',
] as const;

const SHELL_HEADER_FILE = 'src/components/shell/TopHeader/TopHeader.module.css';

const PRIORITY_ROW_FILE = 'src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.module.css';

const ALLOWED_OVERLAY_FILES = new Set([
  'src/components/layout/Modal/Modal.module.css',
  'src/components/layout/Drawer/Drawer.module.css',
  'src/components/layout/Toast/Toast.module.css',
  'src/components/shell/MobileBottomNavigation/MobileBottomNavigation.module.css',
  'src/components/shell/NotificationBell/NotificationBell.module.css',
  'src/components/shell/AuthenticatedAppShell/AuthenticatedAppShell.module.css',
  'src/components/commandCenter/VerifiedRevenueChart/VerifiedRevenueChart.module.css',
  'src/actions/GovernedActionControl.module.css',
  'src/actions/TrustEnvelopeActions.module.css',
]);

const SR_ONLY_PATTERN =
  /(srOnly|sr-only|visuallyHidden|skipLink|liveRegion|tooltip|clip:\s*rect|width:\s*1px)/i;

export interface ReflowOverlapViolation {
  file: string;
  check: string;
  detail: string;
}

function read(rel: string) {
  return readFileSync(join(ROOT, rel), 'utf8');
}

function walkCss(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walkCss(full, acc);
    else if (entry.endsWith('.module.css')) acc.push(relative(ROOT, full).replace(/\\/g, '/'));
  }
  return acc;
}

function hasReflowHeaderRow(content: string): boolean {
  return (
    /composes:\s*pageHeaderRow\s+from\s+['"].*reflowLayout\.module\.css['"]/.test(content) ||
    (/\.headerRow[\s\S]*flex-wrap:\s*wrap/.test(content) && /display:\s*flex/.test(content))
  );
}

export function runReflowOverlapAudit() {
  const violations: ReflowOverlapViolation[] = [];
  const substrate = read(SUBSTRATE_FILE);

  if (!substrate.includes('flex-wrap: wrap') || !substrate.includes('priorityIssueRow')) {
    violations.push({
      file: SUBSTRATE_FILE,
      check: 'substrate-reflow-primitives',
      detail: 'reflow substrate must define wrap + priority row stack rules',
    });
  }

  if (!/--sk-grid-header-action-min-width/.test(read('src/tokens/tokens.css'))) {
    violations.push({
      file: 'src/tokens/tokens.css',
      check: 'header-action-min-width-token',
      detail: 'missing --sk-grid-header-action-min-width',
    });
  }

  const responsiveShellCss = read('src/components/layout/ResponsiveShell/ResponsiveShell.module.css');
  if (
    /\.header[\s\S]*height:\s*var\(--sk-dimension-header-height\)/.test(responsiveShellCss) &&
    !/height:\s*auto/.test(responsiveShellCss)
  ) {
    violations.push({
      file: 'src/components/layout/ResponsiveShell/ResponsiveShell.module.css',
      check: 'shell-header-auto-height',
      detail: 'shell header must use min-height + height:auto so wrapped chrome cannot clip',
    });
  }

  if (!/\.shellHeaderCenter[\s\S]*flex:\s*1\s+1\s+100%/.test(substrate)) {
    violations.push({
      file: SUBSTRATE_FILE,
      check: 'shell-header-stack-default',
      detail: 'shell header zones must default to full-width stack before desktop breakpoint',
    });
  }

  for (const file of PAGE_HEADER_FILES) {
    const content = read(file);
    if (!hasReflowHeaderRow(content)) {
      violations.push({
        file,
        check: 'page-header-flex-wrap',
        detail: 'page header row must use flex-wrap or pageHeaderRow substrate',
      });
    }
    if (/\.page(Subtitle|Question|LastUpdated|Meta)[\s\S]{0,120}white-space:\s*nowrap/.test(content)) {
      violations.push({
        file,
        check: 'page-meta-nowrap-forbidden',
        detail: 'page-level metadata must wrap — remove white-space: nowrap',
      });
    }
  }

  const topHeaderCss = read(SHELL_HEADER_FILE);
  if (
    !/composes:\s*shellHeaderBar/.test(topHeaderCss) ||
    !/justify-content:\s*flex-start/.test(topHeaderCss)
  ) {
    violations.push({
      file: SHELL_HEADER_FILE,
      check: 'shell-header-flex-layout',
      detail: 'TopHeader must use shell header bar with leading sidebar toggle and interface label',
    });
  }

  const priorityCss = read(PRIORITY_ROW_FILE);
  if (
    !/composes:\s*priorityIssueRow/.test(priorityCss) &&
    !/\.priorityRow[\s\S]*max-width:\s*63\.9375rem[\s\S]*grid-template-columns:\s*auto\s+1fr/.test(priorityCss) &&
    !/\.priorityRow[\s\S]*max-width:\s*1023px/.test(priorityCss)
  ) {
    violations.push({
      file: PRIORITY_ROW_FILE,
      check: 'priority-row-stack-breakpoint',
      detail: 'priority queue rows must stack below desktop breakpoint',
    });
  }

  const componentCss = walkCss(join(ROOT, 'src/components'));
  for (const file of componentCss) {
    const content = read(file);
    if (!/position:\s*absolute/.test(content) && !/position:\s*fixed/.test(content)) continue;
    if (ALLOWED_OVERLAY_FILES.has(file)) continue;
    if (
      file.includes('EvidenceTimeline') &&
      /\.item[\s\S]*position:\s*relative/.test(content) &&
      /\.marker[\s\S]*position:\s*absolute/.test(content)
    ) {
      continue;
    }
    if (SR_ONLY_PATTERN.test(content)) continue;

    const blocks = content.split(/\n(?=\.[a-zA-Z])/);
    for (const block of blocks) {
      if (!/position:\s*(absolute|fixed)/.test(block)) continue;
      if (SR_ONLY_PATTERN.test(block)) continue;
      if (/pointer-events:\s*none/.test(block) && /transform:\s*translateY/.test(block)) continue;
      violations.push({
        file,
        check: 'layout-absolute-forbidden',
        detail: 'layout-purpose absolute/fixed positioning detected — use document-flow reflow',
      });
      break;
    }
  }

  const zIndexValues = new Set<number>();
  for (const file of componentCss) {
    const content = read(file);
    for (const match of content.matchAll(/z-index:\s*(\d+)/g)) {
      zIndexValues.add(Number(match[1]));
    }
  }
  const sorted = [...zIndexValues].sort((a, b) => a - b);
  if (sorted.some((z) => z > 100 && z < 900)) {
    violations.push({
      file: 'src/components',
      check: 'z-index-midrange-conflict',
      detail: `orphan z-index values in chrome band: ${sorted.filter((z) => z > 100 && z < 900).join(', ')}`,
    });
  }

  return { violations, filesScanned: PAGE_HEADER_FILES.length + componentCss.length };
}

export const REFLOW_Z_INDEX_LAYERS = {
  chrome: 30,
  drawer: 900,
  modal: 1000,
  toast: 1000,
} as const;
