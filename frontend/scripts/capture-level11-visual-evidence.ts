import { chromium } from 'playwright';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const OUT_DIR = join(process.cwd(), 'evidence', 'Level_11', 'visual');
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'desktop', width: 1280, height: 900 },
];

const CAPTURES: Array<{ path: string; name: string; selector: string }> = [
  {
    path: '/dev/level11-specimens?fixture=billing-loaded',
    name: 'billing-loaded',
    selector: '[data-billing-state="loaded"]',
  },
  {
    path: '/dev/level11-specimens?fixture=route-recovery',
    name: 'route-recovery',
    selector: '[data-route-recovery-panel]',
  },
];

async function startDevServer() {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5211'], {
    shell: true,
    stdio: 'pipe',
  });
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Dev server timeout')), 90000);
    proc.stdout?.on('data', (chunk) => {
      if (String(chunk).includes('5211')) {
        clearTimeout(timeout);
        resolve();
      }
    });
    proc.stderr?.on('data', (chunk) => {
      if (String(chunk).includes('5211')) {
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
        await page.goto(`http://127.0.0.1:5211${capture.path}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
        if (capture.path.includes('billing-loaded')) {
          await page.waitForSelector('[data-level11-specimen-loading]', { state: 'detached', timeout: 10000 }).catch(() => undefined);
        }
        await page.waitForSelector(capture.selector, { timeout: 60000 });
        const file = `${capture.name}-${viewport.name}.png`;
        await page.screenshot({ path: join(OUT_DIR, file), fullPage: true });
        index.push({ file, viewport: viewport.name, specimen: capture.name });
      }
      await context.close();
    }
    writeFileSync(join(OUT_DIR, 'visual-artifact-index.json'), JSON.stringify(index, null, 2));
    for (const entry of index) {
      const filePath = join(OUT_DIR, entry.file);
      if (!existsSync(filePath)) {
        throw new Error(`Missing visual artifact after capture: ${entry.file}`);
      }
    }
    console.log(`Level 11 visual evidence: ${index.length} PNG files verified`);
  } finally {
    await browser.close();
    procKill(server);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
