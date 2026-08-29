import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const OUT_DIR = join(process.cwd(), 'evidence', 'Level_3', 'visual');
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
];

const CAPTURES: Array<{ path: string; name: string }> = [
  { path: '/dev/level3-specimens?fixture=onboarding-step-1-default', name: 'onboarding-step-1-default' },
  { path: '/dev/level3-specimens?fixture=onboarding-step-2-default', name: 'onboarding-step-2-no-commerce' },
  { path: '/dev/level3-specimens?fixture=onboarding-step-3-default', name: 'onboarding-step-3-no-claims' },
  { path: '/dev/level3-specimens?fixture=onboarding-step-3-claim-skip', name: 'onboarding-step-3-skip-warning' },
  { path: '/dev/level3-specimens?fixture=onboarding-step-4-default', name: 'onboarding-step-4-unconfirmed' },
  { path: '/dev/level3-specimens?fixture=onboarding-step-4-privacy-confirmed', name: 'onboarding-step-4-confirmed' },
  { path: '/dev/level3-specimens?fixture=integrations-default', name: 'integrations-default' },
  { path: '/dev/level3-specimens?fixture=commerce-card-connected', name: 'commerce-card-connected' },
  { path: '/dev/level3-specimens?fixture=claim-card-connected', name: 'claim-card-connected' },
  { path: '/dev/level3-specimens?fixture=shell-onboarding', name: 'shell-onboarding-step-1' },
  { path: '/dev/level3-specimens?fixture=shell-integrations', name: 'shell-integrations' },
];

async function startDevServer() {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5199'], {
    shell: true,
    stdio: 'pipe',
  });

  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Dev server timeout')), 60000);
    proc.stdout?.on('data', (chunk) => {
      if (String(chunk).includes('5199')) {
        clearTimeout(timeout);
        resolve();
      }
    });
    proc.stderr?.on('data', (chunk) => {
      if (String(chunk).includes('5199')) {
        clearTimeout(timeout);
        resolve();
      }
    });
  });

  return proc;
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
        await page.goto(`http://127.0.0.1:5199${capture.path}`, { waitUntil: 'networkidle' });
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
    console.log(`Captured ${index.length} Level 3 visual artifacts`);
  } finally {
    await browser.close();
    procKill(server);
  }
}

function procKill(proc: ReturnType<typeof spawn>) {
  proc.kill('SIGTERM');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
