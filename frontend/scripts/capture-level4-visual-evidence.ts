import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const OUT_DIR = join(process.cwd(), 'evidence', 'Level_4', 'visual');
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
];

const CAPTURES: Array<{ path: string; name: string }> = [
  { path: '/dev/level4-specimens?fixture=team-default', name: 'team-default' },
  { path: '/dev/level4-specimens?fixture=team-loading', name: 'team-loading' },
  { path: '/dev/level4-specimens?fixture=team-permission-denied', name: 'team-permission-denied' },
  { path: '/dev/level4-specimens?fixture=policy-default', name: 'policy-default' },
  { path: '/dev/level4-specimens?fixture=policy-blocked', name: 'policy-blocked' },
  { path: '/dev/level4-specimens?fixture=policy-invalid-auto', name: 'policy-invalid-auto-execute' },
  { path: '/dev/level4-specimens?fixture=shell-team', name: 'shell-team' },
  { path: '/dev/level4-specimens?fixture=shell-policy', name: 'shell-policy' },
];

async function startDevServer() {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5200'], {
    shell: true,
    stdio: 'pipe',
  });

  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Dev server timeout')), 60000);
    proc.stdout?.on('data', (chunk) => {
      if (String(chunk).includes('5200')) {
        clearTimeout(timeout);
        resolve();
      }
    });
    proc.stderr?.on('data', (chunk) => {
      if (String(chunk).includes('5200')) {
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
        await page.goto(`http://127.0.0.1:5200${capture.path}`, { waitUntil: 'networkidle' });
        const file = join(OUT_DIR, `${capture.name}-${viewport.name}.png`);
        await page.screenshot({ path: file, fullPage: true });
        index.push({ file, viewport: viewport.name, specimen: capture.name });
        await page.close();
      }
    }

    writeFileSync(
      join(OUT_DIR, 'visual-artifact-index.json'),
      JSON.stringify({ generatedAt: new Date().toISOString(), artifacts: index }, null, 2),
    );
    console.log(`Captured ${index.length} Level 4 visual artifacts`);
  } finally {
    await browser.close();
    procKill(server);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
