#!/usr/bin/env node

/**
 * Package Version Validation Script
 * Ensures @muk223/openapi-contracts and @muk223/api-client versions match
 */

import { readFileSync } from 'fs';

console.log('🔍 Validating @muk223 package version coupling...');
console.log('');

try {
  const pkg = JSON.parse(readFileSync('./package.json', 'utf8'));

  const contractsVersion = pkg.dependencies?.['@muk223/openapi-contracts'];
  const clientVersion = pkg.dependencies?.['@muk223/api-client'];

  console.log('📦 Package Versions:');
  console.log(`   @muk223/openapi-contracts: ${contractsVersion || 'NOT INSTALLED'}`);
  console.log(`   @muk223/api-client:        ${clientVersion || 'NOT INSTALLED'}`);
  console.log('');

  // Check if packages are installed
  if (!contractsVersion || !clientVersion) {
    console.log('⚠️  @muk223 packages not yet installed');
    console.log('   This is acceptable during initial development');
    console.log('');
    console.log('To install:');
    console.log('   npm install @muk223/openapi-contracts@2.0.7 @muk223/api-client@2.0.7');
    console.log('');
    process.exit(0);
  }

  // Check version match
  if (contractsVersion !== clientVersion) {
    console.log('❌ VERSION MISMATCH DETECTED');
    console.log('');
    console.log('   Contracts version: ' + contractsVersion);
    console.log('   Client version:    ' + clientVersion);
    console.log('');
    console.log('These packages MUST be the same version to ensure SDK matches contracts.');
    console.log('');
    console.log('To fix:');
    console.log('   npm install @muk223/openapi-contracts@2.0.7 @muk223/api-client@2.0.7');
    console.log('');
    console.log('See docs/PACKAGE_VERSIONING.md for details');
    process.exit(1);
  }

  // Success
  console.log('✅ Package versions are synchronized: ' + contractsVersion);
  console.log('');
  console.log('Version coupling validated successfully');
  process.exit(0);

} catch (error) {
  console.error('❌ Error reading package.json:', error.message);
  process.exit(1);
}
