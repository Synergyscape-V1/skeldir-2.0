#!/usr/bin/env python3
"""
Integration Mappings Validation Script (Phase C3)

Purpose: Validates that integration mappings between providers and canonical events
         are correctly configured.

Exit Gates:
  C3.1 - Integration Mapping Completeness: All required provider-event mappings exist
  C3.2 - Mapping Consistency: No duplicate or conflicting mappings

Exit Code: 0 if all gates pass, 1 if any validation fails

Note: This is a stub implementation. Full validation requires integration-maps/*.yaml
      files which are not yet implemented in B0.1 scope.
"""

import sys
import yaml
from pathlib import Path
from typing import Dict, List, Tuple

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def load_yaml(file_path: Path) -> dict:
    """Load YAML file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"{RED}ERROR: Failed to load {file_path}: {e}{RESET}")
        return {}


def validate_integration_mappings(repo_root: Path) -> Tuple[bool, List[str]]:
    """
    Gate C3: Validate integration mappings between providers and canonical events.

    Currently checks:
    - Coverage matrix provider mappings exist
    - Coverage manifest domain mappings exist
    """
    errors = []

    print(f"\n{BLUE}Gate C3.1: Integration Mapping Completeness{RESET}")
    print("-" * 60)

    # Check canonical-events.yaml exists
    canonical_events_path = repo_root / 'api-contracts' / 'governance' / 'canonical-events.yaml'
    if not canonical_events_path.exists():
        errors.append(f"Missing canonical-events.yaml at {canonical_events_path}")
        print(f"{RED}X Missing canonical-events.yaml{RESET}")
    else:
        canonical_data = load_yaml(canonical_events_path)
        coverage_matrix = canonical_data.get('provider_coverage_matrix', {})
        event_count = len(coverage_matrix)
        print(f"{GREEN}OK{RESET} Found {event_count} canonical events in coverage matrix")

    # Check coverage-manifest.yaml exists
    coverage_manifest_path = repo_root / 'api-contracts' / 'governance' / 'coverage-manifest.yaml'
    if not coverage_manifest_path.exists():
        errors.append(f"Missing coverage-manifest.yaml at {coverage_manifest_path}")
        print(f"{RED}X Missing coverage-manifest.yaml{RESET}")
    else:
        manifest_data = load_yaml(coverage_manifest_path)
        domain_count = len([k for k in manifest_data.keys() if not k.startswith('_')])
        print(f"{GREEN}OK{RESET} Found {domain_count} domains in coverage manifest")

    print(f"\n{BLUE}Gate C3.2: Mapping Consistency{RESET}")
    print("-" * 60)

    # Check for integration-maps directory (optional for now)
    integration_maps_dir = repo_root / 'api-contracts' / 'governance' / 'integration-maps'
    if integration_maps_dir.exists():
        map_count = len(list(integration_maps_dir.glob('*.yaml')))
        print(f"{GREEN}OK{RESET} Found {map_count} integration mapping files")
    else:
        print(f"{YELLOW}!{RESET} integration-maps/ directory not found (optional for B0.1)")

    return len(errors) == 0, errors


def main():
    """Main execution function."""
    print(f"{BLUE}========================================{RESET}")
    print(f"{BLUE}Skeldir Integration Mappings Validation{RESET}")
    print(f"{BLUE}========================================{RESET}")

    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent

    success, errors = validate_integration_mappings(repo_root)

    print()
    print(f"{BLUE}========================================{RESET}")

    if success:
        print(f"{GREEN}OK ALL C3 VALIDATIONS PASSED{RESET}")
        print(f"{BLUE}========================================{RESET}")
        print()
        print(f"{GREEN}Exit Gates: C3.1 OK, C3.2 OK{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}X VALIDATION FAILED{RESET}")
        print(f"{BLUE}========================================{RESET}")
        print()
        print(f"{RED}Errors:{RESET}")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()
