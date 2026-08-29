import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const OUT_DIR = join(process.cwd(), 'evidence', 'Level_5', 'visual');
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
];

const CAPTURES: Array<{ path: string; name: string }> = [
  { path: '/dev/level5-specimens?fixture=diagnostics-default', name: 'diagnostics-default' },
  { path: '/dev/level5-specimens?fixture=diagnostics-empty', name: 'diagnostics-empty' },
  { path: '/dev/level5-specimens?fixture=diagnostics-permission-denied', name: 'diagnostics-permission-denied' },
  { path: '/dev/level5-specimens?fixture=audit-default', name: 'audit-ledger-default' },
  { path: '/dev/level5-specimens?fixture=audit-empty', name: 'audit-ledger-empty' },
  { path: '/dev/level5-specimens?fixture=audit-permission-denied', name: 'audit-ledger-permission-denied' },
  { path: '/dev/level5-specimens?fixture=artifact-drawer-default', name: 'artifact-drawer-default' },
  { path: '/dev/level5-specimens?fixture=artifact-unavailable', name: 'artifact-unavailable' },
  { path: '/dev/level5-specimens?fixture=artifact-corrupted', name: 'artifact-corrupted' },
  { path: '/dev/level5-specimens?fixture=artifact-access-denied', name: 'artifact-access-denied' },
  { path: '/dev/level5-specimens?fixture=health-operational', name: 'health-operational' },
  { path: '/dev/level5-specimens?fixture=health-degraded', name: 'health-confidence-degraded' },
  { path: '/dev/level5-specimens?fixture=health-paused', name: 'health-api-paused' },
  { path: '/dev/level5-specimens?fixture=health-integration', name: 'health-integration-attention' },
  { path: '/dev/level5-specimens?fixture=health-unknown', name: 'health-unknown' },
  { path: '/dev/level5-specimens?fixture=health-failed', name: 'health-fetch-failed' },
  { path: '/dev/level5-specimens?fixture=shell-audit', name: 'shell-audit-health' },
  { path: '/dev/level5-specimens?fixture=shell-diagnostics', name: 'shell-diagnostics' },
];

async function startDevServer() {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5201'], {
    shell: true,
    stdio: 'pipe',
  });

  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Dev server timeout')), 60000);
    proc.stdout?.on('data', (chunk) => {
      if (String(chunk).includes('5201')) {
        clearTimeout(timeout);
        resolve();
      }
    });
    proc.stderr?.on('data', (chunk) => {
      if (String(chunk).includes('5201')) {
        clearTimeout(timeout);
        resolve();
      }
    });
  });

  return proc;
}

function procKill(proc: ReturnType<typeof spawn>) {
  if (!proc.pid) return;
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

async function main() {
  mkdirSync(OUT_DIR, { recursive: true });
  const server = await startDevServer();
  const browser = await chromium.launch();
  const index: Array<{ file: string; viewport: string; specimen: string }> = [];

  try {
    for (const viewport of VIEWPORTS) {
      for (const capture of CAPTURES) {
        const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
        await page.goto(`http://127.0.0.1:5201${capture.path}`, { waitUntil: 'networkidle' });
        const file = join(OUT_DIR, `${capture.name}-${viewport.name}.png`);
        await page.screenshot({ path: file, fullPage: true });
        index.push({ file: `${capture.name}-${viewport.name}.png`, viewport: viewport.name, specimen: capture.name });
        await page.close();
      }
    }
  } finally {
    await browser.close();
    procKill(server);
  }

  writeFileSync(join(OUT_DIR, 'visual-artifact-index.json'), JSON.stringify({ generatedAt: new Date().toISOString(), artifacts: index }, null, 2));
  console.log(`Captured ${index.length} Level 5 visual artifacts`);
}

void main();
