#!/usr/bin/env python3
"""
Skeldir Contract Coverage Validator
Validates that required provider events in coverage matrix have corresponding OpenAPI operations.

Exit Gates:
- C2.1: Contract Coverage Completeness - Every required provider event has contract operation

Exit code 0: All validations pass
Exit code 1: Validation failures found
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import yaml

# Colors for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def load_yaml(file_path: Path) -> Dict:
    """Load YAML file and return parsed content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"{RED}Error loading {file_path}: {e}{NC}")
        sys.exit(1)


def find_operation_ids_in_contract(contract_data: Dict) -> Set[str]:
    """Extract all operationId values from an OpenAPI contract."""
    operation_ids = set()
    
    paths = contract_data.get('paths', {})
    for path, path_item in paths.items():
        for method in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head']:
            if method in path_item:
                operation = path_item[method]
                if 'operationId' in operation:
                    operation_ids.add(operation['operationId'])
    
    return operation_ids


def validate_contract_coverage(
    coverage_matrix: Dict,
    coverage_manifest: Dict,
    dist_dir: Path,
    repo_root: Path
) -> Tuple[bool, List[str]]:
    """
    Gate C2.1: Verify every required provider event has corresponding OpenAPI operation.
    """
    violations = []
    
    # Collect all operation IDs from bundled contracts
    all_operation_ids = set()
    if dist_dir.exists():
        for contract_file in dist_dir.glob('*.yaml'):
            if contract_file.name.startswith('_'):
                continue  # Skip _common directory files
            contract_data = load_yaml(contract_file)
            ops = find_operation_ids_in_contract(contract_data)
            all_operation_ids.update(ops)
    else:
        violations.append(
            f"{RED}X{NC} Bundled contracts directory not found: {dist_dir}"
        )
        return False, violations
    
    # Check each required event in coverage matrix
    for event_name, providers in coverage_matrix.items():
        for provider_entry in providers:
            if not provider_entry.get("required", False):
                continue  # Skip non-required events
            
            provider = provider_entry.get("provider")
            provider_event = provider_entry.get("provider_event")
            operation_id = provider_entry.get("operation_id")
            
            if not provider_event:
                # N/A case with mitigation - acceptable
                continue
            
            if not operation_id:
                violations.append(
                    f"{YELLOW}!{NC} Event '{event_name}' x Provider '{provider}': "
                    f"required=true but operation_id not specified in coverage matrix"
                )
                continue
            
            # Check if operation exists in contracts
            if operation_id not in all_operation_ids:
                violations.append(
                    f"{RED}X{NC} Event '{event_name}' x Provider '{provider}': "
                    f"operation_id '{operation_id}' NOT FOUND in contracts"
                )
            else:
                print(f"{GREEN}OK{NC} Event '{event_name}' x Provider '{provider}': "
                      f"operation_id '{operation_id}' found")
    
    # Cross-check coverage manifest requirements
    print()
    print(f"{BLUE}Cross-checking coverage manifest...{NC}")
    
    domain_sections = [
        'authentication', 'attribution', 'reconciliation', 'export', 'health',
        'webhooks_shopify', 'webhooks_stripe', 'webhooks_woocommerce', 'webhooks_paypal'
    ]
    
    for domain_name in domain_sections:
        if domain_name not in coverage_manifest:
            continue
        
        domain = coverage_manifest[domain_name]
        requirements = domain.get('requirements', [])
        
        for req in requirements:
            req_id = req.get('requirement_id', 'UNKNOWN')
            operation_id = req.get('operation_id')
            status = req.get('status', 'unknown')
            canonical_event = req.get('canonical_event')
            
            if status == 'implemented' and operation_id:
                if operation_id not in all_operation_ids:
                    violations.append(
                        f"{RED}X{NC} Requirement {req_id}: "
                        f"status='implemented' but operation '{operation_id}' NOT FOUND"
                    )
                else:
                    if canonical_event:
                        print(f"{GREEN}OK{NC} Requirement {req_id}: "
                              f"operation '{operation_id}' -> canonical event '{canonical_event}'")
    
    return len(violations) == 0, violations


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Validate contract coverage completeness'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    args = parser.parse_args()
    
    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    
    print(f"{BLUE}========================================{NC}")
    print(f"{BLUE}Skeldir Contract Coverage Validation{NC}")
    print(f"{BLUE}========================================{NC}")
    print()
    
    # Load canonical events and coverage matrix
    canonical_events_path = repo_root / 'api-contracts' / 'governance' / 'canonical-events.yaml'
    coverage_manifest_path = repo_root / 'api-contracts' / 'governance' / 'coverage-manifest.yaml'
    dist_dir = repo_root / 'api-contracts' / 'dist' / 'openapi' / 'v1'
    
    if not canonical_events_path.exists():
        print(f"{RED}X Canonical events file not found: {canonical_events_path}{NC}")
        sys.exit(1)
    
    if not coverage_manifest_path.exists():
        print(f"{RED}X Coverage manifest file not found: {coverage_manifest_path}{NC}")
        sys.exit(1)
    
    canonical_data = load_yaml(canonical_events_path)
    coverage_manifest = load_yaml(coverage_manifest_path)
    
    coverage_matrix = canonical_data.get('provider_coverage_matrix', {})
    
    # Run validation
    print(f"{BLUE}Gate C2.1: Contract Coverage Completeness{NC}")
    print("-" * 60)
    success, violations = validate_contract_coverage(
        coverage_matrix, coverage_manifest, dist_dir, repo_root
    )
    print()
    
    # Summary
    print(f"{BLUE}========================================{NC}")
    if success:
        print(f"{GREEN}OK ALL VALIDATIONS PASSED{NC}")
        print(f"{GREEN}========================================{NC}")
        print()
        
        # Count required entries
        required_count = sum(
            1 for providers in coverage_matrix.values()
            for entry in providers
            if entry.get("required", False) and entry.get("provider_event")
        )
        
        print(f"{GREEN}Required Events with Contracts: {required_count}{NC}")
        print(f"{GREEN}Exit Gates: C2.1 OK{NC}")
        print()
        sys.exit(0)
    else:
        print(f"{RED}X VALIDATION FAILED{NC}")
        print(f"{RED}========================================{NC}")
        print()
        print(f"{RED}Violations Found:{NC}")
        for violation in violations:
            print(f"  {violation}")
        print()
        print(f"{YELLOW}Action Required:{NC}")
        print(f"  1. Ensure all required provider events have OpenAPI operations")
        print(f"  2. Update operation_id in coverage matrix")
        print(f"  3. Verify contracts are bundled (run bundle.sh)")
        print()
        sys.exit(1)


if __name__ == '__main__':
    main()





