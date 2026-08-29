import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const OUT_DIR = join(process.cwd(), 'evidence', 'Level_8', 'visual');
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
];

const CAPTURES: Array<{ path: string; name: string }> = [
  { path: '/dev/level8-specimens?fixture=claim-detail-loaded', name: 'claim-detail-loaded' },
  { path: '/dev/level8-specimens?fixture=claim-detail-not-found', name: 'claim-detail-error' },
  { path: '/dev/level8-specimens?fixture=trust-detail-loaded', name: 'trust-detail-loaded' },
  { path: '/dev/level8-specimens?fixture=channel-detail-loaded', name: 'channel-detail-loaded' },
  { path: '/dev/level8-specimens?fixture=budget-detail-loaded', name: 'budget-detail-loaded' },
  { path: '/dev/level8-specimens?fixture=exceptions-drawer', name: 'exceptions-queue' },
  { path: '/dev/level8-specimens?fixture=level9-blocked-actions', name: 'level9-blocked-actions' },
];

async function startDevServer() {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5204'], {
    shell: true,
    stdio: 'pipe',
  });
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Dev server timeout')), 60000);
    proc.stdout?.on('data', (chunk) => {
      if (String(chunk).includes('5204')) {
        clearTimeout(timeout);
        resolve();
      }
    });
    proc.stderr?.on('data', (chunk) => {
      if (String(chunk).includes('5204')) {
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
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
      const page = await context.newPage();
      for (const capture of CAPTURES) {
        await page.goto(`http://127.0.0.1:5204${capture.path}`, { waitUntil: 'networkidle' });
        const file = `${capture.name}-${viewport.name}.png`;
        await page.screenshot({ path: join(OUT_DIR, file), fullPage: true });
        index.push({ file, viewport: viewport.name, specimen: capture.name });
      }
      await context.close();
    }
    writeFileSync(join(OUT_DIR, 'visual-artifact-index.json'), JSON.stringify(index, null, 2));
  } finally {
    await browser.close();
    procKill(server);
  }
}

void main();
