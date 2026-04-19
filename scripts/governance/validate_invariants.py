#!/usr/bin/env python3
"""
Skeldir API Invariants Validator
Validates that all fields in contracts match invariant definitions from the registry.
Exit code 0: All validations pass
Exit code 1: Invariant violations found
"""

import sys
import os
import yaml
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

# Colors for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color

def load_yaml(file_path: Path) -> Dict:
    """Load YAML file and return parsed content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"{RED}Error loading {file_path}: {e}{NC}")
        sys.exit(1)

def find_all_schema_fields(schema_data: Dict, parent_path: str = "") -> List[Tuple[str, Dict, str]]:
    """
    Recursively find all fields in schema definitions.
    Returns list of (field_name, field_schema, parent_path) tuples.
    """
    fields = []
    
    if not isinstance(schema_data, dict):
        return fields
    
    # Check components.schemas
    if 'components' in schema_data and 'schemas' in schema_data['components']:
        for schema_name, schema_def in schema_data['components']['schemas'].items():
            if 'properties' in schema_def:
                for prop_name, prop_def in schema_def['properties'].items():
                    field_path = f"{schema_name}.{prop_name}"
                    fields.append((prop_name, prop_def, field_path))
                    
                    # Recursively check nested objects
                    if prop_def.get('type') == 'object' and 'properties' in prop_def:
                        nested_fields = find_nested_fields(prop_def['properties'], field_path)
                        fields.extend(nested_fields)
    
    # Check paths for request/response schemas
    if 'paths' in schema_data:
        for path, path_item in schema_data['paths'].items():
            for method in ['get', 'post', 'put', 'patch', 'delete']:
                if method in path_item:
                    operation = path_item[method]
                    
                    # Check request body
                    if 'requestBody' in operation:
                        req_body = operation['requestBody']
                        if 'content' in req_body:
                            for content_type, content_def in req_body['content'].items():
                                if 'schema' in content_def and 'properties' in content_def['schema']:
                                    for prop_name, prop_def in content_def['schema']['properties'].items():
                                        field_path = f"{path}.{method}.request.{prop_name}"
                                        fields.append((prop_name, prop_def, field_path))
                    
                    # Check responses
                    if 'responses' in operation:
                        for status_code, response_def in operation['responses'].items():
                            if 'content' in response_def:
                                for content_type, content_def in response_def['content'].items():
                                    if 'schema' in content_def and 'properties' in content_def['schema']:
                                        for prop_name, prop_def in content_def['schema']['properties'].items():
                                            field_path = f"{path}.{method}.{status_code}.{prop_name}"
                                            fields.append((prop_name, prop_def, field_path))
    
    return fields

def find_nested_fields(properties: Dict, parent_path: str) -> List[Tuple[str, Dict, str]]:
    """Find fields in nested object properties."""
    fields = []
    for prop_name, prop_def in properties.items():
        field_path = f"{parent_path}.{prop_name}"
        fields.append((prop_name, prop_def, field_path))
        
        if prop_def.get('type') == 'object' and 'properties' in prop_def:
            nested = find_nested_fields(prop_def['properties'], field_path)
            fields.extend(nested)
    
    return fields

def apply_invariant_exceptions(
    invariant_def: Dict,
    contract_name: str,
    field_path: str | None = None,
) -> Dict:
    """Return invariant definition adjusted for contract-specific exceptions."""
    # Copy base definition excluding exceptions metadata
    effective_def = {
        key: value for key, value in invariant_def.items()
        if key != 'exceptions'
    }
    
    exceptions = invariant_def.get('exceptions') or []
    contract_name_lower = contract_name.lower()
    
    for exception in exceptions:
        platform = exception.get('platform')
        if platform and platform.lower() not in contract_name_lower:
            continue

        path_pattern = exception.get('path_pattern')
        if path_pattern and field_path:
            if not re.search(path_pattern, field_path):
                continue
        elif path_pattern and not field_path:
            continue

        for key, value in exception.items():
            if key in {'platform', 'path_pattern'}:
                continue
            effective_def[key] = value
        for key_to_remove in exception.get('unset', []):
            effective_def.pop(key_to_remove, None)
        break
    
    return effective_def


def validate_field_against_invariant(field_name: str, field_schema: Dict, 
                                     invariant_def: Dict, field_path: str) -> List[str]:
    """Validate a single field against its invariant definition."""
    violations = []
    
    # Check type
    expected_type = invariant_def.get('type')
    actual_type = field_schema.get('type')
    
    if expected_type and actual_type != expected_type:
        violations.append(
            f"  {field_path}: type mismatch (expected {expected_type}, got {actual_type})"
        )
    
    # Check pattern
    if 'pattern' in invariant_def:
        if 'pattern' not in field_schema:
            violations.append(
                f"  {field_path}: missing pattern constraint (expected: {invariant_def['pattern']})"
            )
        elif field_schema['pattern'] != invariant_def['pattern']:
            violations.append(
                f"  {field_path}: pattern mismatch "
                f"(expected {invariant_def['pattern']}, got {field_schema['pattern']})"
            )
    
    # Check format
    if 'format' in invariant_def:
        if 'format' not in field_schema:
            violations.append(
                f"  {field_path}: missing format constraint (expected: {invariant_def['format']})"
            )
        elif field_schema['format'] != invariant_def['format']:
            violations.append(
                f"  {field_path}: format mismatch "
                f"(expected {invariant_def['format']}, got {field_schema['format']})"
            )
    
    # Check minimum
    if 'minimum' in invariant_def:
        if 'minimum' not in field_schema:
            violations.append(
                f"  {field_path}: missing minimum constraint (expected: {invariant_def['minimum']})"
            )
        elif field_schema['minimum'] != invariant_def['minimum']:
            violations.append(
                f"  {field_path}: minimum mismatch "
                f"(expected {invariant_def['minimum']}, got {field_schema['minimum']})"
            )
    
    # Check maximum
    if 'maximum' in invariant_def:
        if 'maximum' not in field_schema:
            violations.append(
                f"  {field_path}: missing maximum constraint (expected: {invariant_def['maximum']})"
            )
        elif field_schema['maximum'] != invariant_def['maximum']:
            violations.append(
                f"  {field_path}: maximum mismatch "
                f"(expected {invariant_def['maximum']}, got {field_schema['maximum']})"
            )
    
    # Check enum
    if 'enum' in invariant_def:
        if 'enum' not in field_schema:
            violations.append(
                f"  {field_path}: missing enum constraint (expected: {invariant_def['enum']})"
            )
        elif set(field_schema['enum']) != set(invariant_def['enum']):
            violations.append(
                f"  {field_path}: enum mismatch "
                f"(expected {invariant_def['enum']}, got {field_schema['enum']})"
            )
    
    return violations

def validate_invariants(repo_root: Path, verbose: bool = False) -> Tuple[bool, List[str], Dict]:
    """
    Validate all contracts against invariants registry.
    Returns (success, violations, statistics)
    """
    invariants_path = repo_root / 'api-contracts' / 'governance' / 'invariants.yaml'
    dist_dir = repo_root / 'api-contracts' / 'dist' / 'openapi' / 'v1'
    
    # Load invariants registry
    if not invariants_path.exists():
        return False, [f"Invariants registry not found: {invariants_path}"], {}
    
    invariants = load_yaml(invariants_path)
    domain_invariants = invariants.get('domain_invariants', {})
    
    if not domain_invariants:
        return False, ["No domain invariants defined in registry"], {}
    
    # Collect all violations
    violations = []
    stats = {
        'contracts_checked': 0,
        'fields_validated': 0,
        'invariant_checks_performed': 0,
        'violations_found': 0
    }
    
    # Check bundled contracts
    if not dist_dir.exists():
        return False, [f"Bundled contracts directory not found: {dist_dir}"], {}
    
    for contract_file in dist_dir.glob('*.bundled.yaml'):
        stats['contracts_checked'] += 1
        contract_data = load_yaml(contract_file)
        
        if verbose:
            print(f"  Checking {contract_file.name}...")
        
        # Find all fields in contract
        fields = find_all_schema_fields(contract_data)
        stats['fields_validated'] += len(fields)
        
        # Check each field against invariants
        for field_name, field_schema, field_path in fields:
            # Look for matching invariant
            for invariant_name, invariant_def in domain_invariants.items():
                # Match field name to invariant name
                # Handle special cases: currency_stripe vs currency
                if invariant_name == field_name or \
                   (invariant_name == 'currency_stripe' and field_name == 'currency' and 'stripe' in contract_file.name.lower()):
                    stats['invariant_checks_performed'] += 1
                    
                    effective_invariant = apply_invariant_exceptions(
                        invariant_def, contract_file.name, field_path
                    )
                    
                    field_violations = validate_field_against_invariant(
                        field_name, field_schema, effective_invariant, field_path
                    )
                    
                    if field_violations:
                        violations.append(f"{RED}✗{NC} {contract_file.name}:")
                        violations.extend(field_violations)
                        stats['violations_found'] += len(field_violations)
    
    success = len(violations) == 0
    return success, violations, stats

def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Validate API contracts against invariants registry'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')
    args = parser.parse_args()
    
    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    
    print(f"{GREEN}========================================{NC}")
    print(f"{GREEN}Skeldir API Invariants Validation{NC}")
    print(f"{GREEN}========================================{NC}")
    print()
    
    success, violations, stats = validate_invariants(repo_root, args.verbose)
    
    if args.json:
        result = {
            'success': success,
            'violations': [v.replace(RED, '').replace(YELLOW, '').replace(GREEN, '').replace(NC, '') 
                          for v in violations],
            'statistics': stats
        }
        print(json.dumps(result, indent=2))
        sys.exit(0 if success else 1)
    
    # Print statistics
    print(f"{GREEN}Invariants Validation Statistics:{NC}")
    print(f"  Contracts Checked: {stats['contracts_checked']}")
    print(f"  Fields Validated: {stats['fields_validated']}")
    print(f"  Invariant Checks Performed: {stats['invariant_checks_performed']}")
    print(f"  Violations Found: {stats['violations_found']}")
    print()
    
    if violations:
        print(f"{RED}✗ Invariant Violations Found:{NC}")
        print()
        for violation in violations:
            print(violation)
        print()
        print(f"{RED}========================================{NC}")
        print(f"{RED}✗ INVARIANTS VALIDATION FAILED{NC}")
        print(f"{RED}========================================{NC}")
        print()
        print(f"{YELLOW}Action Required:{NC}")
        print(f"  1. Review violations and update contract schemas")
        print(f"  2. Ensure all constrained fields match invariant registry definitions")
        print(f"  3. Consider updating invariants registry if business requirements changed")
        print()
        sys.exit(1)
    else:
        print(f"{GREEN}✓ All invariant validations passed{NC}")
        print()
        print(f"{GREEN}========================================{NC}")
        print(f"{GREEN}✓ INVARIANTS VALIDATION COMPLETE{NC}")
        print(f"{GREEN}========================================{NC}")
        print()
        sys.exit(0)

if __name__ == '__main__':
    main()





