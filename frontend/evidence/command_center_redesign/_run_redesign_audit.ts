import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';

const OUT = join(process.cwd(), 'evidence', 'command_center_redesign');
const VIS = join(OUT, 'visual');
const COMPUTED = join(OUT, 'computed');
const TESTS = join(OUT, 'tests');
const ASSETS = join(OUT, 'assets');

for (const dir of [VIS, COMPUTED, TESTS, ASSETS]) {
  mkdirSync(dir, { recursive: true });
}

const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
];

const STATE_FIXTURES = [
  { fixture: 'command-center-loaded', file: 'priority-issues', wait: '[data-command-center-loaded="true"]' },
  { fixture: 'command-center-no-priority', file: 'no-priority', wait: '[data-command-center-loaded="true"]' },
  { fixture: 'command-center-trust-api-failed', file: 'trust-api-error', wait: '[data-command-center-trust-api-error]' },
  { fixture: 'command-center-kill-switch', file: 'kill-switch', wait: '[data-command-center-kill-switch-banner]' },
  { fixture: 'command-center-loading-delayed', file: 'loading-delayed', wait: '[data-command-center-loading="true"]' },
  { fixture: 'command-center-partial', file: 'partial-data', wait: '[data-command-center-loaded="true"]' },
  { fixture: 'command-center-trend-unavailable', file: 'trend-unavailable', wait: '[data-trend-unavailable]' },
];

async function startDev(): Promise<ChildProcess> {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5213'], {
    shell: true,
    stdio: 'pipe',
  });
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('Dev server timeout')), 90000);
    const onData = (chunk: Buffer) => {
      if (String(chunk).includes('5213')) {
        clearTimeout(t);
        resolve();
      }
    };
    proc.stdout?.on('data', onData);
    proc.stderr?.on('data', onData);
  });
  return proc;
}

function kill(proc: ChildProcess | null) {
  if (!proc?.pid) return;
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { shell: true, stdio: 'ignore' });
    return;
  }
  try {
    proc.kill('SIGTERM');
  } catch {
    /* ignore */
  }
}

async function getComputed(page: import('playwright').Page, selector: string) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      selector: sel,
      text: (el.textContent || '').trim().slice(0, 200),
      fontSize: cs.fontSize,
      lineHeight: cs.lineHeight,
      fontWeight: cs.fontWeight,
      color: cs.color,
      backgroundColor: cs.backgroundColor,
      padding: cs.padding,
      gap: cs.gap,
      minHeight: cs.minHeight,
      outline: cs.outline,
      boundingBox: { x: r.x, y: r.y, width: r.width, height: r.height },
    };
  }, selector);
}

async function main() {
  const server = await startDev();
  const browser = await chromium.launch();
  const screenshots: Array<Record<string, unknown>> = [];
  const computed: Record<string, unknown> = {};
  const overflow: Record<string, unknown> = {};

  try {
    const desktopCtx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const desktopPage = await desktopCtx.newPage();
    await desktopPage.goto('http://127.0.0.1:5213/dev/level10-specimens?fixture=command-center-loaded', {
      waitUntil: 'networkidle',
      timeout: 90000,
    });
    await desktopPage.waitForURL('**/app', { timeout: 90000 });
    await desktopPage.waitForSelector('[data-command-center-loaded="true"]', { timeout: 90000 });

    const selectors = [
      '[data-command-center-header]',
      '[data-command-center-last-updated]',
      '[data-command-center-urgency]',
      '[data-command-center-primary-action] a',
      '[data-summary-metric="verified_revenue"] [class*="metricValue"]',
      '[data-summary-drilldown="verified_revenue"]',
      '[data-priority-queue]',
      '[data-verified-revenue-chart], [data-trend-unavailable]',
      '[data-platform-claim-label]',
      '[data-discrepancy-badge]',
      '[data-shell-brand]',
      '[data-notification-bell]',
      '[data-shell-sidebar] a[aria-current="page"]',
    ];
    for (const sel of selectors) {
      computed[sel] = await getComputed(desktopPage, sel);
    }

    computed.layout = await desktopPage.evaluate(() => {
      const grid = document.querySelector('[class*="gridTwo"]');
      if (!grid) return null;
      const cs = getComputedStyle(grid);
      const children = [...grid.children].map((c) => ({
        width: c.getBoundingClientRect().width,
        trend: c.getAttribute('data-verified-revenue-trend'),
        channel: c.getAttribute('data-channel-trust-table'),
      }));
      return { gridTemplateColumns: cs.gridTemplateColumns, gap: cs.gap, children };
    });

    await desktopCtx.close();

    for (const vp of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await ctx.newPage();
      await page.goto('http://127.0.0.1:5213/dev/level10-specimens?fixture=command-center-loaded', {
        waitUntil: 'networkidle',
        timeout: 90000,
      });
      await page.waitForURL('**/app', { timeout: 90000 });
      await page.waitForSelector('[data-command-center-loaded="true"]', { timeout: 90000 });
      const file = `${vp.name === 'desktop' ? 'desktop-1280' : vp.name === 'wide' ? 'wide-1440' : vp.name}-loaded.png`;
      await page.screenshot({ path: join(VIS, file), fullPage: true });
      screenshots.push({
        file,
        viewport: vp.name,
        width: vp.width,
        route: '/app',
        fixture: 'command-center-loaded',
        timestamp: new Date().toISOString(),
      });
      overflow[vp.name] = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      }));
      await ctx.close();
    }

    for (const state of STATE_FIXTURES) {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await ctx.newPage();
      await page.goto(`http://127.0.0.1:5213/dev/level10-specimens?fixture=${state.fixture}`, {
        waitUntil: 'networkidle',
        timeout: 90000,
      });
      await page.waitForURL('**/app', { timeout: 90000 });
      await page.waitForSelector(state.wait, { timeout: 90000 });
      const file = `${state.file}.png`;
      await page.screenshot({ path: join(VIS, file), fullPage: true });
      screenshots.push({
        file,
        viewport: 'desktop-1280',
        route: '/app',
        fixture: state.fixture,
        timestamp: new Date().toISOString(),
      });
      await ctx.close();
    }

    writeFileSync(join(COMPUTED, 'computed-styles-command-center.json'), JSON.stringify(computed, null, 2));
    writeFileSync(join(COMPUTED, 'layout-measurements.json'), JSON.stringify(computed.layout ?? {}, null, 2));
    writeFileSync(join(COMPUTED, 'overflow-results.json'), JSON.stringify(overflow, null, 2));
    writeFileSync(join(OUT, 'runtime-screenshots.json'), JSON.stringify(screenshots, null, 2));
    writeFileSync(
      join(VIS, 'trend-available-or-not-testable.md'),
      computed['[data-verified-revenue-chart], [data-trend-unavailable]']
        ? '# Trend available in default loaded fixture (chart or unavailable panel present in DOM).'
        : '# Trend state not captured.',
    );
    console.log('REDESIGN_AUDIT_OK', screenshots.length);
  } finally {
    await browser.close();
    kill(server);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
