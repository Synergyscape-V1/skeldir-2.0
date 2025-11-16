#!/bin/bash
# Git Commit Preparation Script
# Purpose: Group restructuring changes into logical commits for clean git history
# Usage: ./prepare-git-commits.sh

set -euo pipefail

echo "=========================================="
echo "Git Commit Preparation"
echo "=========================================="
echo ""
echo "This script will help you create logical commits for the restructuring."
echo "All changes will be staged in groups for review before committing."
echo ""

# Check if git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not a git repository"
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "Warning: You have uncommitted changes"
    echo "Current status:"
    git status --short
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Creating logical commit groups..."
echo ""

# Group 1: Contract Reorganization
echo "Group 1: Contract Reorganization"
git add contracts/attribution/ contracts/webhooks/ contracts/auth/ contracts/reconciliation/ contracts/export/ contracts/health/ contracts/_common/
git add contracts/baselines/ 2>/dev/null || true
git add docker-compose.yml  # Updated contract paths
echo "✓ Staged contract reorganization"
echo ""

# Group 2: Database Migration Reorganization
echo "Group 2: Database Migration Reorganization"
git add alembic.ini
git add alembic/versions/001_core_schema/ alembic/versions/002_pii_controls/ alembic/versions/003_data_governance/
git add scripts/database/
echo "✓ Staged migration reorganization"
echo ""

# Group 3: Documentation Consolidation
echo "Group 3: Documentation Consolidation"
git add docs/database/ docs/architecture/ docs/operations/
git add docs/archive/implementation-phases/b0.3/
echo "✓ Staged documentation consolidation"
echo ""

# Group 4: Service Boundaries & Dockerization
echo "Group 4: Service Boundaries & Dockerization"
git add backend/app/*/Dockerfile
git add docker-compose.component-dev.yml
git add docs/architecture/service-boundaries.md
echo "✓ Staged service boundaries"
echo ""

# Group 5: Environment Configuration
echo "Group 5: Environment Configuration"
git add .env.example
echo "✓ Staged environment configuration"
echo ""

# Group 6: Monitoring & Operations
echo "Group 6: Monitoring & Operations"
git add monitoring/
git add docs/operations/
echo "✓ Staged monitoring configuration"
echo ""

# Group 7: CI/CD Updates
echo "Group 7: CI/CD Updates"
git add .github/workflows/
git add scripts/generate-models.sh
git add scripts/detect-breaking-changes.sh
git add package.json
echo "✓ Staged CI/CD updates"
echo ""

# Group 8: Contributing & Documentation Updates
echo "Group 8: Contributing & Documentation Updates"
git add CONTRIBUTING.md
git add backend/README.md
echo "✓ Staged documentation updates"
echo ""

# Group 9: Deployment Scripts
echo "Group 9: Deployment Scripts"
git add scripts/deployment/
echo "✓ Staged deployment scripts"
echo ""

echo "=========================================="
echo "Staging Complete"
echo "=========================================="
echo ""
echo "All changes have been staged in logical groups."
echo ""
echo "Next steps:"
echo "1. Review staged changes: git status"
echo "2. Review specific group: git diff --cached"
echo "3. Create commits for each group:"
echo "   git commit -m 'refactor(contracts): reorganize into domain-based structure'"
echo "   git commit -m 'refactor(database): group migrations by logical function'"
echo "   git commit -m 'docs: consolidate B0.3 documentation into functional categories'"
echo "   git commit -m 'feat(services): add Dockerfiles and service boundaries'"
echo "   git commit -m 'feat(config): add comprehensive environment configuration'"
echo "   git commit -m 'feat(monitoring): add PII monitoring and alerting'"
echo "   git commit -m 'ci: update workflows for new repository structure'"
echo "   git commit -m 'docs: update contributing guidelines for new structure'"
echo "   git commit -m 'chore(deployment): add pre-deployment validation scripts'"
echo ""
echo "4. Create feature branch: git checkout -b feature/repository-restructuring"
echo "5. Push to GitHub: git push origin feature/repository-restructuring"
echo ""

