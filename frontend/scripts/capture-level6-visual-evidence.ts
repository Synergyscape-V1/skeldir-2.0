import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const OUT_DIR = join(process.cwd(), 'evidence', 'Level_6', 'visual');
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
];

const CAPTURES: Array<{ path: string; name: string }> = [
  { path: '/dev/level6-specimens?fixture=locked-commerce', name: 'step5-locked-commerce' },
  { path: '/dev/level6-specimens?fixture=waiting-event', name: 'step5-waiting-event' },
  { path: '/dev/level6-specimens?fixture=step-5-ready', name: 'step5-ready' },
  { path: '/dev/level6-specimens?fixture=generation-success', name: 'step5-generation-success' },
  { path: '/dev/level6-specimens?fixture=generation-failed', name: 'step5-generation-failed' },
  { path: '/dev/level6-specimens?fixture=payload-oversized', name: 'step5-payload-oversized' },
  { path: '/dev/level6-specimens?fixture=schema-invalid', name: 'step5-schema-invalid' },
  { path: '/dev/level6-specimens?fixture=confidence-available', name: 'step5-confidence-available' },
  { path: '/dev/level6-specimens?fixture=already-generated', name: 'step5-already-generated' },
  { path: '/dev/level6-specimens?fixture=step-6', name: 'step6-default' },
  { path: '/dev/level6-specimens?fixture=step-6-permission-denied', name: 'step6-permission-denied' },
  { path: '/dev/level6-specimens?fixture=shell-step-5', name: 'shell-onboarding-step5' },
  { path: '/dev/level6-specimens?fixture=shell-step-6', name: 'shell-onboarding-step6' },
];

async function startDevServer() {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5202'], {
    shell: true,
    stdio: 'pipe',
  });

  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Dev server timeout')), 60000);
    proc.stdout?.on('data', (chunk) => {
      if (String(chunk).includes('5202')) {
        clearTimeout(timeout);
        resolve();
      }
    });
    proc.stderr?.on('data', (chunk) => {
      if (String(chunk).includes('5202')) {
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
        await page.goto(`http://127.0.0.1:5202${capture.path}`, { waitUntil: 'networkidle' });
        const file = `${capture.name}-${viewport.name}.png`;
        await page.screenshot({ path: join(OUT_DIR, file), fullPage: true });
        index.push({ file, viewport: viewport.name, specimen: capture.name });
      }
      await context.close();
    }
    writeFileSync(join(OUT_DIR, 'visual-artifact-index.json'), JSON.stringify(index, null, 2));
    console.log(`Captured ${index.length} Level 6 visual artifacts`);
  } finally {
    await browser.close();
    procKill(server);
  }
}

void main();
