#!/usr/bin/env node

/**
 * Frontend Contracts Integration - SHA256 Checksum Validator
 * 
 * Validates contract file integrity by comparing current file hashes against
 * stored checksums. Blocks CI pipeline on any mismatch.
 * 
 * Usage: node scripts/validate-checksums.js
 * Exit Codes:
 *   0 - All checksums valid
 *   1 - Validation failed (checksum mismatch or missing files)
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CONTRACTS_DIR = path.join(__dirname, '../docs/api/contracts');
const CHECKSUMS_FILE = path.join(__dirname, '../checksums.json');

/**
 * Generate SHA256 hash for a file
 * @param {string} filePath - Path to the file
 * @returns {string} SHA256 hash in hex format
 */
function generateSHA256(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex');
}

/**
 * Validate contract checksums
 * @returns {boolean} True if all checksums valid, false otherwise
 */
function validateChecksums() {
  console.log('🔍 Validating contract file checksums...\n');

  // Check if checksums file exists
  if (!fs.existsSync(CHECKSUMS_FILE)) {
    console.error(`❌ Error: Checksums file not found: ${CHECKSUMS_FILE}`);
    console.error('   Run: npm run generate:checksums');
    return false;
  }

  // Check if contracts directory exists
  if (!fs.existsSync(CONTRACTS_DIR)) {
    console.error(`❌ Error: Contracts directory not found: ${CONTRACTS_DIR}`);
    return false;
  }

  // Load checksums
  const checksums = JSON.parse(fs.readFileSync(CHECKSUMS_FILE, 'utf8'));
  console.log(`📄 Loaded checksums generated at: ${checksums.generated_at}`);
  console.log(`🔐 Algorithm: ${checksums.algorithm}\n`);

  let allValid = true;
  let validCount = 0;
  let failedCount = 0;
  let missingCount = 0;

  // Validate each contract file
  for (const [relativePath, expectedHash] of Object.entries(checksums.contracts)) {
    const fullPath = path.join(CONTRACTS_DIR, relativePath);

    if (!fs.existsSync(fullPath)) {
      console.error(`❌ MISSING: ${relativePath}`);
      console.error(`   Expected hash: ${expectedHash}`);
      missingCount++;
      allValid = false;
      continue;
    }

    const actualHash = generateSHA256(fullPath);

    if (actualHash === expectedHash) {
      console.log(`✓ VALID: ${relativePath}`);
      validCount++;
    } else {
      console.error(`❌ MISMATCH: ${relativePath}`);
      console.error(`   Expected: ${expectedHash}`);
      console.error(`   Actual:   ${actualHash}`);
      failedCount++;
      allValid = false;
    }
  }

  console.log('\n' + '='.repeat(60));
  console.log('Validation Summary:');
  console.log(`  ✓ Valid:   ${validCount}`);
  console.log(`  ❌ Failed:  ${failedCount}`);
  console.log(`  ⚠️  Missing: ${missingCount}`);
  console.log('='.repeat(60));

  if (allValid) {
    console.log('\n✅ All contract checksums valid');
    console.log('🚀 Contract integrity verified - safe to proceed\n');
  } else {
    console.log('\n❌ Checksum validation FAILED');
    console.log('🚨 Contract integrity compromised - blocking pipeline\n');
    console.log('Actions:');
    console.log('  1. If contracts were intentionally updated:');
    console.log('     Run: npm run generate:checksums');
    console.log('  2. If contracts were NOT updated:');
    console.log('     Investigate unauthorized modifications\n');
  }

  return allValid;
}

try {
  const isValid = validateChecksums();
  process.exit(isValid ? 0 : 1);
} catch (error) {
  console.error('❌ Error validating checksums:', error.message);
  process.exit(1);
}
