#!/usr/bin/env node

/**
 * Frontend Contracts Integration - SHA256 Checksum Generator
 * 
 * Generates cryptographic checksums for all OpenAPI contract files to ensure
 * contract integrity and detect unauthorized modifications.
 * 
 * Usage: node scripts/generate-checksums.js
 * Output: checksums.json with SHA256 hashes for all contract files
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CONTRACTS_DIR = path.join(__dirname, '../docs/api/contracts');
const OUTPUT_FILE = path.join(__dirname, '../checksums.json');

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
 * Recursively find all YAML files in directory
 * @param {string} dir - Directory to search
 * @param {string[]} fileList - Accumulated file list
 * @returns {string[]} List of YAML file paths
 */
function findYAMLFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);

  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      findYAMLFiles(filePath, fileList);
    } else if (file.endsWith('.yaml') || file.endsWith('.yml')) {
      fileList.push(filePath);
    }
  });

  return fileList;
}

/**
 * Generate checksums for all contract files
 */
function generateChecksums() {
  console.log('🔐 Generating SHA256 checksums for contract files...\n');

  if (!fs.existsSync(CONTRACTS_DIR)) {
    console.error(`❌ Error: Contracts directory not found: ${CONTRACTS_DIR}`);
    process.exit(1);
  }

  const yamlFiles = findYAMLFiles(CONTRACTS_DIR);

  if (yamlFiles.length === 0) {
    console.error('❌ Error: No YAML contract files found');
    process.exit(1);
  }

  const checksums = {
    generated_at: new Date().toISOString(),
    algorithm: 'SHA256',
    contracts: {}
  };

  yamlFiles.forEach(filePath => {
    const relativePath = path.relative(CONTRACTS_DIR, filePath);
    const hash = generateSHA256(filePath);
    checksums.contracts[relativePath] = hash;
    console.log(`✓ ${relativePath}: ${hash}`);
  });

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(checksums, null, 2));

  console.log(`\n✅ Generated checksums for ${yamlFiles.length} contract files`);
  console.log(`📄 Output saved to: ${OUTPUT_FILE}`);
  console.log(`\nChecksum Summary:`);
  console.log(`  Algorithm: ${checksums.algorithm}`);
  console.log(`  Generated: ${checksums.generated_at}`);
  console.log(`  Files: ${Object.keys(checksums.contracts).length}`);
}

try {
  generateChecksums();
} catch (error) {
  console.error('❌ Error generating checksums:', error.message);
  process.exit(1);
}
