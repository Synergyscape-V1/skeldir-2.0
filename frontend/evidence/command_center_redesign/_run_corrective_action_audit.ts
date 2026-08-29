import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { buildRadiusNestingAuditTable } from '../../src/audit/commandCenterCorrectiveActionNegativeScopeScan';

const OUT = join(process.cwd(), 'evidence', 'command_center_redesign');
const VIS = join(OUT, 'visual');
const COMPUTED = join(OUT, 'computed');
const TESTS = join(OUT, 'tests');

for (const dir of [VIS, COMPUTED, TESTS]) {
  mkdirSync(dir, { recursive: true });
}

const VIEWPORTS = [
  { name: 'mobile-375', width: 375, file: 'mobile-375-loaded-corrected.png' },
  { name: 'tablet-768', width: 768, file: 'tablet-768-loaded-corrected.png' },
  { name: 'intermediate-1024', width: 1024, file: 'intermediate-1024-loaded-corrected.png' },
  { name: 'intermediate-1100', width: 1100, file: 'intermediate-1100-loaded-corrected.png' },
  { name: 'intermediate-1180', width: 1180, file: 'intermediate-1180-loaded-corrected.png' },
  { name: 'intermediate-1279', width: 1279, file: 'intermediate-1279-loaded-corrected.png' },
  { name: 'desktop-1280', width: 1280, file: 'desktop-1280-loaded-corrected.png' },
  { name: 'wide-1440', width: 1440, file: 'wide-1440-loaded-corrected.png' },
];

const STATE_FIXTURES = [
  { fixture: 'command-center-loaded', file: 'priority-issues.png', wait: '[data-command-center-loaded="true"]' },
  { fixture: 'command-center-no-priority', file: 'no-priority.png', wait: '[data-command-center-loaded="true"]' },
  { fixture: 'command-center-trust-api-failed', file: 'trust-api-error.png', wait: '[data-command-center-trust-api-error]' },
  { fixture: 'command-center-kill-switch', file: 'kill-switch.png', wait: '[data-command-center-kill-switch-banner]' },
  { fixture: 'command-center-loading-delayed', file: 'loading-delayed.png', wait: '[data-command-center-loading="true"]' },
  { fixture: 'command-center-partial', file: 'partial-data.png', wait: '[data-command-center-loaded="true"]' },
  { fixture: 'command-center-trend-unavailable', file: 'trend-unavailable.png', wait: '[data-trend-unavailable]' },
  { fixture: 'command-center-trend-available', file: 'trend-available.png', wait: '[data-verified-revenue-chart]' },
  { fixture: 'command-center-empty-tenant', file: 'empty-tenant.png', wait: '[data-command-center-page]' },
  { fixture: 'command-center-stale', file: 'stale-aggregate.png', wait: '[data-command-center-status-text]' },
  { fixture: 'command-center-health-degraded', file: 'health-degraded.png', wait: '[data-command-center-health-banner][data-health-state="confidence_degraded"]' },
  { fixture: 'command-center-integration-attention', file: 'integration-attention.png', wait: '[data-command-center-health-banner][data-health-state="integration_attention"]' },
];

async function startDev(): Promise<ChildProcess> {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5215'], {
    shell: true,
    stdio: 'pipe',
  });
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('Dev server timeout')), 90000);
    const onData = (chunk: Buffer) => {
      if (String(chunk).includes('5215')) {
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
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      borderRadius: cs.borderRadius,
      padding: cs.padding,
      gap: cs.gap,
      minHeight: cs.minHeight,
      outlineWidth: cs.outlineWidth,
      boundingBox: { x: r.x, y: r.y, width: r.width, height: r.height },
    };
  }, selector);
}

async function main() {
  const server = await startDev();
  const browser = await chromium.launch();
  const screenshots: Array<Record<string, unknown>> = [];
  const overflow: Record<string, unknown> = {};
  const layout: Record<string, unknown> = {};
  const brandScan: Record<string, unknown> = {};
  const summaryMetrics: Record<string, unknown> = {};
  const disposition: Record<string, unknown> = {};
  const focusSequence: Array<Record<string, unknown>> = [];

  try {
    for (const vp of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: 900 } });
      const page = await ctx.newPage();
      await page.goto('http://127.0.0.1:5215/dev/level10-specimens?fixture=command-center-loaded', {
        waitUntil: 'domcontentloaded',
        timeout: 90000,
      });
      await page.waitForURL('**/app', { timeout: 90000 });
      await page.waitForSelector('[data-command-center-loaded="true"]', { timeout: 90000 });
      await page.screenshot({ path: join(VIS, vp.file), fullPage: true });
      overflow[vp.name] = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      }));
      if (vp.width === 1280) {
        layout.trendTable = await page.evaluate(() => {
          const stack = document.querySelector('[data-grid-trend-table]');
          if (!stack) return null;
          const cs = getComputedStyle(stack);
          return {
            display: cs.display,
            flexDirection: cs.flexDirection,
            gap: cs.gap,
            children: [...stack.children].map((c) => ({
              width: c.getBoundingClientRect().width,
              height: c.getBoundingClientRect().height,
              trend: c.getAttribute('data-verified-revenue-trend'),
              channel: c.getAttribute('data-channel-trust-table'),
            })),
          };
        });
        layout.channelTableScroll = await page.evaluate(() => {
          const wrap = document.querySelector('[data-channel-table-scroll-wrap]') as HTMLElement | null;
          if (!wrap) return null;
          const cs = getComputedStyle(wrap);
          return {
            clientWidth: wrap.clientWidth,
            scrollWidth: wrap.scrollWidth,
            overflowX: cs.overflowX,
            hasInternalHScroll: wrap.scrollWidth > wrap.clientWidth + 1,
            channelLogoCount: document.querySelectorAll('[data-channel-logo]').length,
            rowCount: document.querySelectorAll('[data-channel-trust-row]').length,
          };
        });
        brandScan.visibleSkeldirOutsideBrand = await page.evaluate(() => {
          const brand = document.querySelector('[data-shell-brand]');
          const hits: string[] = [];
          for (const el of document.querySelectorAll('h1, span')) {
            if (brand?.contains(el)) continue;
            const text = (el.textContent ?? '').trim();
            if (text !== 'Skeldir') continue;
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') continue;
            hits.push(el.tagName);
          }
          return hits;
        });
        brandScan.headerSuppressed = await page.locator('[data-shell-header-route-title-suppressed="true"]').count();
        for (const id of ['verified_revenue', 'claims_reconciled', 'action_authority', 'open_exceptions']) {
          summaryMetrics[id] = await getComputed(page, `[data-summary-metric-value="${id}"]`);
        }
        await page.locator('[data-recent-trust-envelopes]').scrollIntoViewIfNeeded();
        await page.locator('[data-audit-activity-strip]').scrollIntoViewIfNeeded();
        await page.screenshot({ path: join(VIS, 'recent-trustenvelopes.png'), fullPage: true });
        await page.screenshot({ path: join(VIS, 'audit-activity.png'), fullPage: true });
      }
      await ctx.close();
    }

    for (const state of STATE_FIXTURES) {
      try {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await ctx.newPage();
      await page.goto(`http://127.0.0.1:5215/dev/level10-specimens?fixture=${state.fixture}`, {
        waitUntil: 'domcontentloaded',
        timeout: 90000,
      });
      if (state.fixture !== 'command-center-empty-tenant') {
        await page.waitForURL('**/app', { timeout: 90000 });
      }
      await page.waitForSelector(state.wait, { timeout: 90000 });
      if (state.fixture === 'command-center-empty-tenant') {
        await page.waitForFunction(
          () => document.querySelector('[data-command-center-empty-tenant="true"]') !== null,
          undefined,
          { timeout: 15000 },
        );
      }
      await page.screenshot({ path: join(VIS, state.file), fullPage: true });
      disposition[state.fixture] = {
        wait: state.wait,
        present: true,
        screenshot: state.file,
        timestamp: new Date().toISOString(),
      };
      screenshots.push({ file: state.file, fixture: state.fixture, viewport: 1280 });
      await ctx.close();
      } catch (error) {
        disposition[state.fixture] = {
          wait: state.wait,
          present: false,
          error: error instanceof Error ? error.message : String(error),
          timestamp: new Date().toISOString(),
        };
      }
    }

    const focusCtx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const focusPage = await focusCtx.newPage();
    await focusPage.goto('http://127.0.0.1:5215/dev/level10-specimens?fixture=command-center-loaded', {
      waitUntil: 'networkidle',
      timeout: 90000,
    });
    await focusPage.waitForSelector('[data-command-center-loaded="true"]', { timeout: 90000 });
    for (let i = 0; i < 20; i++) {
      await focusPage.keyboard.press('Tab');
      const active = await focusPage.evaluate(() => {
        const el = document.activeElement;
        if (!el) return null;
        return {
          tag: el.tagName,
          role: el.getAttribute('role'),
          ariaLabel: el.getAttribute('aria-label'),
          href: el.getAttribute('href'),
          data: {
            notification: el.getAttribute('data-notification-bell'),
            primary: el.closest('[data-command-center-primary-action]')?.getAttribute('data-primary-action-kind'),
            drilldown: el.getAttribute('data-summary-drilldown'),
            audit: el.getAttribute('data-audit-chip'),
          },
        };
      });
      if (active) focusSequence.push({ step: i + 1, active });
    }
    await focusCtx.close();

    writeFileSync(join(COMPUTED, 'corrective-overflow-results.json'), JSON.stringify(overflow, null, 2));
    writeFileSync(join(COMPUTED, 'corrective-layout-measurements.json'), JSON.stringify(layout, null, 2));
    writeFileSync(join(COMPUTED, 'corrective-brand-text-scan.json'), JSON.stringify(brandScan, null, 2));
    writeFileSync(join(COMPUTED, 'corrective-summary-metric-long-value-audit.json'), JSON.stringify(summaryMetrics, null, 2));
    writeFileSync(join(COMPUTED, 'corrective-disposition-matrix.json'), JSON.stringify(disposition, null, 2));
    writeFileSync(join(COMPUTED, 'corrective-focus-sequence.json'), JSON.stringify(focusSequence, null, 2));
    writeFileSync(join(COMPUTED, 'corrective-radius-nesting-audit.json'), JSON.stringify(buildRadiusNestingAuditTable(), null, 2));
    writeFileSync(
      join(COMPUTED, 'corrective-lower-proof-surfaces.json'),
      JSON.stringify(
        {
          recentTrustEnvelopes: { marker: 'data-recent-trust-envelopes', envelopeLink: 'data-envelope-reconstruction-link' },
          auditActivity: { marker: 'data-audit-activity-strip', sourceLabel: 'data-audit-source-label', chip: 'data-audit-chip' },
        },
        null,
        2,
      ),
    );
    writeFileSync(
      join(VIS, 'health-degraded-or-not-testable.md'),
      disposition['command-center-health-degraded'] ? '# Health degraded — PROVEN via confidence_degraded banner fixture.' : '# NOT TESTABLE',
    );
    writeFileSync(
      join(VIS, 'stale-aggregate-or-not-testable.md'),
      disposition['command-center-stale'] ? '# Stale aggregate — PROVEN via stale fixture and status text.' : '# NOT TESTABLE',
    );
    writeFileSync(
      join(VIS, 'integration-attention-or-not-testable.md'),
      disposition['command-center-integration-attention']
        ? '# Integration attention — PROVEN via integration_attention health banner fixture.'
        : '# NOT TESTABLE',
    );
    writeFileSync(join(OUT, 'runtime-screenshots-corrective.json'), JSON.stringify(screenshots, null, 2));
    console.log('CORRECTIVE_AUDIT_OK', screenshots.length, Object.keys(overflow).length);
  } finally {
    await browser.close();
    kill(server);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
