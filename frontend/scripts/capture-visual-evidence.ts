import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const OUT_DIR = join(process.cwd(), 'evidence', 'Level_0', 'visual');
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'wide', width: 1440, height: 900 },
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
  const index: Array<{ file: string; viewport: string; specimen?: string }> = [];

  try {
    for (const viewport of VIEWPORTS) {
      const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
      await page.goto('http://127.0.0.1:5199/', { waitUntil: 'networkidle' });

      const fullPath = join(OUT_DIR, `specimen-gallery-${viewport.name}.png`);
      await page.screenshot({ path: fullPath, fullPage: true });
      index.push({ file: fullPath, viewport: viewport.name });

      const specimens = page.locator('[data-specimen]');
      const count = await specimens.count();
      for (let i = 0; i < count; i++) {
        const el = specimens.nth(i);
        const name = (await el.getAttribute('data-specimen')) ?? `specimen-${i}`;
        const shot = join(OUT_DIR, `${name}-${viewport.name}.png`);
        await el.screenshot({ path: shot });
        index.push({ file: shot, viewport: viewport.name, specimen: name });
      }

      await page.close();
    }

    const manifest = join(OUT_DIR, 'visual-artifact-index.json');
    await import('node:fs').then(({ writeFileSync }) =>
      writeFileSync(manifest, JSON.stringify({ generatedAt: new Date().toISOString(), artifacts: index }, null, 2)),
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
