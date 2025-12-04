import { exec } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

// Load registry
const registryPath = path.join(__dirname, '../scripts/contracts/mock-registry.json');
const registry = JSON.parse(fs.readFileSync(registryPath, 'utf-8'));

const CONTRACTS_DIR = path.join(__dirname, '../api-contracts/dist/openapi/v1');

const startMock = (name: string, port: number, contractFile: string) => {
  const bundlePath = path.join(CONTRACTS_DIR, contractFile.replace('.yaml', '.bundled.yaml'));

  if (!fs.existsSync(bundlePath)) {
    console.error(`[ERROR] Bundle not found for ${name}: ${bundlePath}`);
    return;
  }

  console.log(`[START] Starting ${name} on port ${port}...`);
  const prism = exec(`npx prism mock "${bundlePath}" -p ${port} -h 0.0.0.0`);

  prism.stdout?.on('data', (data) => console.log(`[${name}] ${data.trim()}`));
  prism.stderr?.on('data', (data) => console.error(`[${name} ERR] ${data.trim()}`));
};

// Start Core
registry.contracts.core.forEach((c: any) => startMock(c.name, c.port, c.contract));
// Start Webhooks
registry.contracts.webhooks.forEach((c: any) => startMock(c.name, c.port, c.contract));
// Start LLM (B0.2 Focus)
registry.contracts.llm.forEach((c: any) => startMock(c.name, c.port, c.contract));

console.log('--- All Mocks Initialized ---');
