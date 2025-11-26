#!/usr/bin/env node

/**
 * Mock Server Manager
 * Starts and manages all Mockoon mock servers for testing
 * Keeps servers alive until manually stopped (Ctrl+C)
 */

import { spawn } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, '..');

const mockServers = [
  { name: 'Authentication', port: 4010, file: 'auth.json' },
  { name: 'Attribution', port: 4011, file: 'attribution.json' },
  { name: 'Reconciliation', port: 4012, file: 'reconciliation.json' },
  { name: 'Export', port: 4013, file: 'export.json' },
  { name: 'Health Monitoring', port: 4014, file: 'health.json' },
];

const processes = [];

console.log('🚀 Starting Mockoon Mock Servers');
console.log('='.repeat(50));
console.log('');

// Start all mock servers
mockServers.forEach((server) => {
  const envFile = join(projectRoot, 'mockoon', 'environments', server.file);
  
  console.log(`✓ Starting: ${server.name} (port ${server.port})`);
  
  const proc = spawn('npx', [
    'mockoon-cli',
    'start',
    '--data',
    envFile,
    '--port',
    server.port.toString()
  ], {
    stdio: ['ignore', 'pipe', 'pipe'],
    cwd: projectRoot
  });

  proc.stdout.on('data', (data) => {
    const message = data.toString().trim();
    if (message) {
      try {
        const parsed = JSON.parse(message);
        if (parsed.level === 'info' && parsed.message.includes('started')) {
          console.log(`  ✓ ${server.name} ready on port ${server.port}`);
        }
      } catch (e) {
        // Not JSON, just log it
        console.log(`  [${server.name}] ${message}`);
      }
    }
  });

  proc.stderr.on('data', (data) => {
    console.error(`  [${server.name} ERROR] ${data.toString().trim()}`);
  });

  proc.on('error', (err) => {
    console.error(`  ✗ Failed to start ${server.name}:`, err.message);
  });

  proc.on('exit', (code) => {
    console.log(`  ✗ ${server.name} exited with code ${code}`);
  });

  processes.push({ name: server.name, process: proc });
});

console.log('');
console.log('='.repeat(50));
console.log('');
console.log('All mock servers started!');
console.log('');
console.log('Available services:');
mockServers.forEach((server) => {
  console.log(`  • ${server.name}: http://localhost:${server.port}`);
});
console.log('');
console.log('Health check: npm run mocks:health');
console.log('Press Ctrl+C to stop all servers');
console.log('');

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('');
  console.log('🛑 Stopping all mock servers...');
  
  processes.forEach(({ name, process: proc }) => {
    console.log(`  Stopping ${name}...`);
    proc.kill('SIGTERM');
  });

  setTimeout(() => {
    console.log('');
    console.log('All servers stopped.');
    process.exit(0);
  }, 1000);
});

// Keep process alive
process.stdin.resume();
