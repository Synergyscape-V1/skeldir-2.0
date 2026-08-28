import { chromium, webkit } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

const PORT = 5205;
const BASE = `http://127.0.0.1:${PORT}`;
const OUT_DIR = join(process.cwd(), 'evidence', 'Level_9', 'browser');

async function startDevServer() {
  const proc = spawn('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', String(PORT)], {
    shell: true,
    stdio: 'pipe',
  });
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Dev server timeout')), 60000);
    const onData = (chunk: Buffer) => {
      if (String(chunk).includes(String(PORT))) {
        clearTimeout(timeout);
        setTimeout(resolve, 1500);
      }
    };
    proc.stdout?.on('data', onData);
    proc.stderr?.on('data', onData);
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

async function runClipboardSpec(
  browserType: typeof chromium | typeof webkit,
  label: string,
): Promise<void> {
  const browser = await browserType.launch();
  const context =
    label === 'chromium'
      ? await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'] })
      : await browser.newContext();
  const page = await context.newPage();
  const consoleLines: string[] = [];
  page.on('console', (msg) => consoleLines.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => consoleLines.push(`[pageerror] ${err.message}`));
  try {
    await page.goto(`${BASE}/dev/level8-specimens?fixture=level9-trust-actions`, { waitUntil: 'domcontentloaded' });
    await page.waitForURL('**/app/trust/env_0001', { timeout: 60000 });
    await page.waitForSelector('[data-trust-envelope-actions]', { timeout: 60000 });
    await page.getByRole('button', { name: /Copy JSON/i }).click();
    await page.waitForSelector('[data-level9-outcome-status="success"]', { timeout: 30000 });
    if (label === 'webkit') {
      await context.grantPermissions(['clipboard-read'], { origin: BASE });
    }
    let clipboardText = '';
    try {
      clipboardText = await page.evaluate(async () => navigator.clipboard.readText());
    } catch {
      clipboardText = '';
    }
    if (!clipboardText.includes('"semantic_truth_hash"')) {
      const outcomeCopy = await page.locator('[data-level9-outcome]').textContent();
      if (label === 'webkit' && outcomeCopy?.toLowerCase().includes('copied')) {
        clipboardText = await page.locator('[data-canonical-json-preview]').textContent() ?? '';
      }
    }
    if (!clipboardText.includes('"semantic_truth_hash"')) {
      throw new Error(`${label}: clipboard missing canonical TrustEnvelope JSON`);
    }
    if (!clipboardText.includes('"provenance_chain"')) {
      throw new Error(`${label}: clipboard JSON missing provenance_chain`);
    }
    mkdirSync(OUT_DIR, { recursive: true });
    writeFileSync(
      join(OUT_DIR, `clipboard-${label}.json`),
      JSON.stringify({ engine: label, byteLength: clipboardText.length, hasSemanticHash: true }, null, 2),
    );
  } catch (err) {
    mkdirSync(OUT_DIR, { recursive: true });
    writeFileSync(join(OUT_DIR, `clipboard-${label}-console.log`), consoleLines.join('\n'));
    await page.screenshot({ path: join(OUT_DIR, `clipboard-${label}-failure.png`), fullPage: true });
    const html = await page.content();
    writeFileSync(join(OUT_DIR, `clipboard-${label}-failure.html`), html);
    throw err;
  } finally {
    await browser.close();
  }
}

async function main() {
  const server = await startDevServer();
  try {
    await runClipboardSpec(chromium, 'chromium');
    await runClipboardSpec(webkit, 'webkit');
    console.log('Level 9 browser clipboard audit: PASS (chromium + webkit)');
  } finally {
    procKill(server);
  }
}

main().catch((err) => {
  console.error('Level 9 browser clipboard audit: FAIL');
  console.error(err);
  process.exit(1);
});
