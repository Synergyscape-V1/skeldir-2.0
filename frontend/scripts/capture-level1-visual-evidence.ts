import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const OUT_DIR = join(process.cwd(), 'evidence', 'Level_1', 'visual');
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
];

const CAPTURES: Array<{ path: string; name: string }> = [
  { path: '/login', name: 'login-default' },
  { path: '/login?reason=session_expired', name: 'login-session-expired' },
  { path: '/signup', name: 'signup-default' },
  { path: '/dev/auth-specimens?fixture=login-invalid', name: 'login-invalid-credentials' },
  { path: '/dev/auth-specimens?fixture=login-network', name: 'login-network-failure' },
  { path: '/dev/auth-specimens?fixture=login-oauth-pending', name: 'login-oauth-pending' },
  { path: '/dev/auth-specimens?fixture=login-oauth-error', name: 'login-oauth-error' },
  { path: '/dev/auth-specimens?fixture=login-unsafe-redirect', name: 'login-unsafe-redirect-blocked' },
  { path: '/dev/auth-specimens?fixture=signup-invalid-email', name: 'signup-invalid-business-email' },
  { path: '/dev/auth-specimens?fixture=signup-tenant-exists', name: 'signup-tenant-already-exists' },
  { path: '/dev/auth-specimens?fixture=signup-tenant-pending', name: 'signup-tenant-creation-pending' },
  { path: '/dev/auth-specimens?fixture=signup-tenant-failed', name: 'signup-tenant-creation-failed' },
  { path: '/dev/auth-specimens?fixture=signup-handoff', name: 'signup-post-signup-handoff' },
  { path: '/dev/auth-specimens?fixture=oauth-buttons', name: 'oauth-button-states' },
  { path: '/dev/auth-specimens?fixture=business-email', name: 'business-email-input-states' },
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
    console.log(JSON.stringify({ outputDir: OUT_DIR, count: index.length }, null, 2));
  } finally {
    await browser.close();
    server.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
