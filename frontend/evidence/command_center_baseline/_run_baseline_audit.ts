import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';

const OUT = join(process.cwd(), 'evidence', 'command_center_baseline');
const VIS = join(OUT, 'visual');
mkdirSync(VIS, { recursive: true });

const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
];

async function startDev(): Promise<ChildProcess> {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5211'], {
    shell: true,
    stdio: 'pipe',
  });
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('Dev server timeout')), 90000);
    const onData = (chunk: Buffer) => {
      if (String(chunk).includes('5211')) {
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
      borderColor: cs.borderColor,
      borderRadius: cs.borderRadius,
      padding: cs.padding,
      width: cs.width,
      height: cs.height,
      display: cs.display,
      gridTemplateColumns: cs.gridTemplateColumns,
      gap: cs.gap,
      boxShadow: cs.boxShadow,
      boundingBox: { x: r.x, y: r.y, width: r.width, height: r.height },
    };
  }, selector);
}

async function main() {
  const server = await startDev();
  const browser = await chromium.launch();
  const computed: Record<string, unknown> = {};
  const screenshots: Array<Record<string, unknown>> = [];
  const overflow: Record<string, unknown> = {};

  try {
    for (const vp of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await ctx.newPage();
      await page.goto('http://127.0.0.1:5211/dev/level10-specimens?fixture=command-center-loaded', {
        waitUntil: 'networkidle',
        timeout: 60000,
      });
      await page.waitForURL('**/app', { timeout: 60000 });
      await page.waitForSelector('[data-command-center-loaded="true"]', { timeout: 60000 });
      const file = `app-loaded-${vp.name}.png`;
      await page.screenshot({ path: join(VIS, file), fullPage: true });
      screenshots.push({
        file,
        viewport: vp.name,
        width: vp.width,
        height: vp.height,
        url: page.url(),
        timestamp: new Date().toISOString(),
        dataState: 'loaded-default-fixture',
        browser: 'chromium-playwright',
        route: 'real /app after Level10 specimen session bootstrap',
      });
      overflow[vp.name] = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      }));

      if (vp.name === 'desktop') {
        const selectors = [
          '[data-viewport="app-shell"] aside',
          '[data-shell-sidebar]',
          '[data-shell-sidebar] a[aria-current="page"]',
          '[data-shell-header]',
          '[data-command-center-header] h1',
          '[data-command-center-last-updated]',
          '[data-command-center-primary-action] a',
          '[data-summary-metric="verified_revenue"] .metricValue',
          '[data-summary-metric="verified_revenue"]',
          '[data-priority-queue]',
          '[data-verified-revenue-trend]',
          '[data-channel-trust-table]',
          '[data-system-status-pill]',
          '[data-tenant-selector]',
          '[data-user-menu]',
        ];
        for (const sel of selectors) {
          computed[sel] = await getComputed(page, sel);
        }
        computed.gridTwo = await page.evaluate(() => {
          const grid = document.querySelector('[class*="gridTwo"]');
          if (!grid) return null;
          const cs = getComputedStyle(grid);
          const children = [...grid.children].map((c) => {
            const r = c.getBoundingClientRect();
            return {
              width: r.width,
              attrs: {
                trend: c.getAttribute('data-verified-revenue-trend'),
                channel: c.getAttribute('data-channel-trust-table'),
              },
            };
          });
          return {
            gridTemplateColumns: cs.gridTemplateColumns,
            gap: cs.gap,
            parentWidth: grid.getBoundingClientRect().width,
            children,
          };
        });
        computed.navItems = await page.evaluate(() =>
          [...document.querySelectorAll('[data-shell-sidebar] .navItemLabel, [data-shell-sidebar] a span')].map(
            (el) => (el.textContent || '').trim(),
          ),
        );
        computed.priorityCopy = await page.evaluate(() => {
          const rows = [...document.querySelectorAll('[data-priority-issue]')].map((el) => ({
            title: el.querySelector('strong')?.textContent?.trim(),
            explanation: el.querySelector('p')?.textContent?.trim(),
          }));
          return rows;
        });
      }

      await ctx.close();
    }

    writeFileSync(join(OUT, 'runtime-screenshots.json'), JSON.stringify(screenshots, null, 2));
    writeFileSync(join(OUT, 'computed-styles-desktop.json'), JSON.stringify(computed, null, 2));
    writeFileSync(join(OUT, 'overflow-by-viewport.json'), JSON.stringify(overflow, null, 2));
    console.log('AUDIT_OK', screenshots.length);
  } finally {
    await browser.close();
    kill(server);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
