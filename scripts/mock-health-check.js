#!/usr/bin/env node

/**
 * Mock Server Health Check Utility
 * Verifies connectivity to all 10 Prism mock servers (4010-4019)
 */

import { randomUUID } from 'crypto';

const mockServers = [
  { name: 'Attribution API', port: 4010, path: '/api/attribution/revenue/realtime' },
  { name: 'Health Monitoring API', port: 4011, path: '/api/health' },
  { name: 'Export API', port: 4012, path: '/api/export/csv' },
  { name: 'Reconciliation API', port: 4013, path: '/api/reconciliation/status' },
  { name: 'Error Logging API', port: 4014, path: '/api/errors/log' },
  { name: 'Authentication API', port: 4015, path: '/api/auth/verify' },
  { name: 'Shopify Webhooks', port: 4016, path: '/webhooks/shopify/order' },
  { name: 'WooCommerce Webhooks', port: 4017, path: '/webhooks/woocommerce/order' },
  { name: 'Stripe Webhooks', port: 4018, path: '/webhooks/stripe/payment' },
  { name: 'PayPal Webhooks', port: 4019, path: '/webhooks/paypal/payment' }
];

async function checkServer(server) {
  const url = `http://localhost:${server.port}${server.path}`;
  
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'X-Correlation-ID': randomUUID(),
        'Authorization': 'Bearer mock-token-for-health-check'
      }
    });
    
    const status = response.status;
    const isHealthy = status >= 200 && status < 500; // Mock server responding
    
    return {
      name: server.name,
      port: server.port,
      status: isHealthy ? '✓ ONLINE' : '✗ ERROR',
      httpStatus: status,
      url
    };
  } catch (error) {
    return {
      name: server.name,
      port: server.port,
      status: '✗ OFFLINE',
      httpStatus: null,
      url,
      error: error.message
    };
  }
}

async function main() {
  console.log('🔍 Mock Server Health Check (10 Servers: 4010-4019)');
  console.log('=' .repeat(60));
  console.log('');
  
  const results = await Promise.all(mockServers.map(checkServer));
  
  let onlineCount = 0;
  let offlineCount = 0;
  
  results.forEach(result => {
    const statusColor = result.status.includes('ONLINE') ? '\x1b[32m' : '\x1b[31m';
    const resetColor = '\x1b[0m';
    
    console.log(`${statusColor}${result.status}${resetColor} ${result.name}`);
    console.log(`   Port: ${result.port}`);
    console.log(`   URL: ${result.url}`);
    
    if (result.httpStatus !== null) {
      console.log(`   HTTP: ${result.httpStatus}`);
      onlineCount++;
    } else {
      console.log(`   Error: ${result.error}`);
      offlineCount++;
    }
    
    console.log('');
  });
  
  console.log('=' .repeat(60));
  console.log(`Summary: ${onlineCount} online, ${offlineCount} offline (of ${mockServers.length} total)`);
  console.log('');
  
  if (offlineCount > 0) {
    console.log('⚠️  Some mock servers are offline.');
    console.log('   Start with: bash scripts/start-mock-servers.sh');
    process.exit(1);
  } else {
    console.log('✅ All 10 mock servers are responding!');
    process.exit(0);
  }
}

main().catch(err => {
  console.error('Health check failed:', err);
  process.exit(1);
});
