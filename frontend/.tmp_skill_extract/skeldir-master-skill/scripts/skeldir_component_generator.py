#!/usr/bin/env python3
"""
skeldir_component_generator.py

Generates production-ready Skeldir React/TypeScript components with:
- Correct state machine (loading/empty/error/ready)
- Design token imports (no hardcoded values)
- TypeScript interface contract first
- Psychological load audit checklist
- Correct copy from templates

Usage:
    python scripts/skeldir_component_generator.py <ComponentName> [--type card|table|chart|page]

Examples:
    python scripts/skeldir_component_generator.py MetricCard --type card
    python scripts/skeldir_component_generator.py ChannelTable --type table
    python scripts/skeldir_component_generator.py BudgetOptimizer --type page
"""

import argparse
import os
import sys
from pathlib import Path

COMPONENT_TYPES = ['card', 'table', 'chart', 'page', 'modal', 'form']

TOKENS_IMPORT = """import {
  colors,
  typography,
  spacing,
  radius,
  motion,
  shadows,
  getConfidenceTokens,
  getDiscrepancyTokens,
  type ConfidenceLevel,
} from '../../tokens/design-tokens';"""

STATE_MACHINE_TYPES = """
// ─── SKELDIR STANDARD: All 4 states must be handled ────────────────
type ComponentState =
  | { status: 'loading' }
  | { status: 'empty';  emptyVariant: 'no-data-yet' | 'building-model' | 'no-results-filter' | 'feature-locked' }
  | { status: 'error';  error: { message: string; correlationId: string; retryable: boolean; action?: { label: string; onClick: () => void } } }
  | { status: 'ready';  data: {COMPONENT_NAME}Data }
"""

SKELETON_COMPONENT = """
const {COMPONENT_NAME}Skeleton: React.FC = () => (
  <div style={{
    background: colors.bgSecondary,
    border: `1px solid ${colors.borderSubtle}`,
    borderRadius: radius.lg,
    padding: spacing['6'],
    animation: 'shimmer 1.6s ease-in-out infinite',
  }}>
    {/* Skeleton structure mirrors ready state layout */}
    <div style={{
      background: colors.bgTertiary,
      height: '14px',
      width: '40%',
      borderRadius: radius.sm,
      marginBottom: spacing['3'],
    }} />
    <div style={{
      background: colors.bgTertiary,
      height: '36px',
      width: '65%',
      borderRadius: radius.sm,
    }} />
    <style>{`
      @keyframes shimmer {
        0%, 100% { opacity: 0.6; }
        50%       { opacity: 1.0; }
      }
    `}</style>
  </div>
);"""

EMPTY_STATE_COMPONENT = """
const {COMPONENT_NAME}EmptyState: React.FC<{ variant: string }> = ({ variant }) => {
  const config = {
    'no-data-yet':        { message: 'Connect your first platform to begin attribution modeling.', action: 'Connect Platform' },
    'building-model':     { message: 'Accumulating evidence for your first model.', action: null },
    'no-results-filter':  { message: 'No results match this filter. Adjust range or clear filters.', action: 'Clear Filters' },
    'feature-locked':     { message: 'Available on Agency plan.', action: 'View Plans' },
  }[variant] ?? { message: 'No data available.', action: null };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing['12'],
      color: colors.textSecondary,
      fontFamily: typography.fontBody,
      textAlign: 'center',
    }}>
      <p style={{ fontSize: typography.scale.bodyMd.size, marginBottom: spacing['4'] }}>
        {config.message}
      </p>
      {config.action && (
        <button style={{
          background: colors.brandPrimary,
          color: colors.textInverse,
          border: 'none',
          borderRadius: radius.md,
          padding: `${spacing['2']} ${spacing['4']}`,
          fontSize: typography.scale.bodyMd.size,
          fontWeight: 600,
          cursor: 'pointer',
          fontFamily: typography.fontBody,
        }}>
          {config.action}
        </button>
      )}
    </div>
  );
};"""

ERROR_STATE_COMPONENT = """
const {COMPONENT_NAME}ErrorState: React.FC<{
  message: string;
  correlationId: string;
  retryable: boolean;
  action?: { label: string; onClick: () => void };
}> = ({ message, correlationId, retryable, action }) => (
  <div style={{
    background: colors.confidenceLowBg,
    border: `1px solid ${colors.confidenceLowBorder}`,
    borderRadius: radius.lg,
    padding: spacing['6'],
    fontFamily: typography.fontBody,
  }}>
    <p style={{ color: colors.textPrimary, fontSize: typography.scale.bodyLg.size, marginBottom: spacing['2'] }}>
      {message}
    </p>
    <p style={{ color: colors.textMuted, fontSize: typography.scale.bodySm.size, marginBottom: spacing['4'] }}>
      Error ID: {correlationId}
    </p>
    <div style={{ display: 'flex', gap: spacing['3'] }}>
      {retryable && (
        <button style={{
          background: colors.brandPrimary,
          color: colors.textInverse,
          border: 'none',
          borderRadius: radius.md,
          padding: `${spacing['2']} ${spacing['4']}`,
          cursor: 'pointer',
          fontFamily: typography.fontBody,
          fontSize: typography.scale.bodyMd.size,
          fontWeight: 600,
        }}>
          Retry
        </button>
      )}
      {action && (
        <button
          onClick={action.onClick}
          style={{
            background: 'transparent',
            color: colors.textSecondary,
            border: `1px solid ${colors.borderDefault}`,
            borderRadius: radius.md,
            padding: `${spacing['2']} ${spacing['4']}`,
            cursor: 'pointer',
            fontFamily: typography.fontBody,
            fontSize: typography.scale.bodyMd.size,
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  </div>
);"""

MAIN_COMPONENT_TEMPLATE = """
// ─── PROPS CONTRACT (read this before reading implementation) ──────
/**
 * {COMPONENT_NAME} — {COMPONENT_DESCRIPTION}
 *
 * Persona: {PERSONA}
 * Screen layer: {LAYER}
 * Live polling: {LIVE_POLLING}
 */
export interface {COMPONENT_NAME}Data {{
  // TODO: Define data shape from backend API response
  // Rule: Name fields by what they ARE, not generic 'data' or 'items'
}}

export interface {COMPONENT_NAME}Props {{
  state: ComponentState;
  // TODO: Add remaining props following naming conventions:
  // - confidence: ConfidenceLevel (not 'level' or 'status')
  // - verifiedRevenue: string (pre-formatted, not 'value' or 'amount')
  // - onActionClick: () => void (not 'handler' or 'callback')
}}

// ─── IMPLEMENTATION ───────────────────────────────────────────────
const {COMPONENT_NAME}Ready: React.FC<{COMPONENT_NAME}Props & {{ state: Extract<ComponentState, {{ status: 'ready' }}> }}> = ({ state, ...props }) => {{
  // TODO: Implement nominal state render
  // Checklist before declaring complete:
  // [ ] No hardcoded colors (use tokens)
  // [ ] No calculations visible to user (Zero Mental Math)
  // [ ] Confidence signal visible without hover
  // [ ] Primary action is single and prominent
  // [ ] All metric values use fontData (IBM Plex Mono)

  return (
    <div style={{{{
      background: colors.bgSecondary,
      border: `1px solid ${{colors.borderSubtle}}`,
      borderRadius: radius.lg,
      padding: spacing['6'],
      fontFamily: typography.fontBody,
    }}}}>
      <p style={{{{ color: colors.textSecondary, fontSize: typography.scale.bodyMd.size }}}}>
        {COMPONENT_NAME} — implement nominal state
      </p>
    </div>
  );
}};

export const {COMPONENT_NAME}: React.FC<{COMPONENT_NAME}Props> = (props) => {{
  // STATE MACHINE — all 4 states handled, no implicit states allowed
  if (props.state.status === 'loading') return <{COMPONENT_NAME}Skeleton />;
  if (props.state.status === 'error')   return <{COMPONENT_NAME}ErrorState {{...props.state.error}} />;
  if (props.state.status === 'empty')   return <{COMPONENT_NAME}EmptyState variant={{props.state.emptyVariant}} />;
  return <{COMPONENT_NAME}Ready {{...props}} state={{props.state}} />;
}};

export default {COMPONENT_NAME};
"""

PSYCHOLOGICAL_AUDIT = """
/*
 * ═══════════════════════════════════════════════════════════════
 * PSYCHOLOGICAL LOAD AUDIT — complete before merging
 * ═══════════════════════════════════════════════════════════════
 *
 * MEMORY LOAD:
 * [ ] User does not need information from a previous screen
 * [ ] All required context is visible in this component
 * [ ] State is preserved on navigate-away and return
 *
 * DECISION LOAD:
 * [ ] Maximum ONE primary action presented
 * [ ] Secondary actions are visually subordinate
 * [ ] Default state is correct for 80% of users 80% of the time
 *
 * INFERENCE LOAD:
 * [ ] No calculations required (all comparisons pre-computed)
 * [ ] Color meaning is explained on first encounter
 * [ ] Confidence terminology: only "High/Medium/Low", no synonyms
 *
 * ANXIETY LOAD:
 * [ ] Error states are recoverable (action button present)
 * [ ] Loading states communicate what is happening
 * [ ] Destructive actions have confirmation with consequence preview
 * ═══════════════════════════════════════════════════════════════
 */
"""

def generate_component(name: str, component_type: str, output_dir: str):
    """Generate a complete Skeldir component file."""

    persona_map = {
        'card':  'Agency Director (11PM, fragmented attention, <5min)',
        'table': 'Marketing Manager (CFO pressure, needs defensible number)',
        'chart': 'Marketing Manager (CFO pressure, needs defensible number)',
        'page':  'Agency Director + Marketing Manager',
        'modal': 'Both personas — high-stakes decision confirmation',
        'form':  'Marketing Manager — data entry flow',
    }

    layer_map = {
        'card':  'Layer 1: Command (Action) — 95% of users stay here',
        'table': 'Layer 2: Model Explorer (Understanding)',
        'chart': 'Layer 2: Model Explorer (Understanding)',
        'page':  'Layer 1: Command (Action)',
        'modal': 'Layer 1: Command (Action) — confirmation flow',
        'form':  'Layer 3: Data Deep Dive (Validation)',
    }

    lines = [
        "/**",
        f" * {name}",
        f" * Type: {component_type}",
        " *",
        " * AUTO-GENERATED by skeldir_component_generator.py",
        " * Follows: Skeldir Master Skill SKILL.md",
        " *",
        " * DO NOT modify token imports. DO NOT hardcode values.",
        " * Complete the TODO sections and run the Psychological Load Audit.",
        " */",
        "",
        "import React from 'react';",
        TOKENS_IMPORT,
        "",
        PSYCHOLOGICAL_AUDIT,
        "",
        STATE_MACHINE_TYPES.replace('{COMPONENT_NAME}', name),
        "",
        SKELETON_COMPONENT.replace('{COMPONENT_NAME}', name),
        "",
        EMPTY_STATE_COMPONENT.replace('{COMPONENT_NAME}', name),
        "",
        ERROR_STATE_COMPONENT.replace('{COMPONENT_NAME}', name),
        "",
        MAIN_COMPONENT_TEMPLATE
            .replace('{COMPONENT_NAME}', name)
            .replace('{COMPONENT_DESCRIPTION}', f'Skeldir {component_type} component')
            .replace('{PERSONA}', persona_map.get(component_type, 'Both personas'))
            .replace('{LAYER}', layer_map.get(component_type, 'Layer 1'))
            .replace('{LIVE_POLLING}', 'Yes — add usePolling(30000) if this shows live metrics' if component_type in ['card', 'page'] else 'No'),
    ]

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{name}.tsx")

    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))

    print(f"✓ Generated: {filepath}")
    print(f"\nNext steps:")
    print(f"  1. Define {name}Data interface with exact backend API fields")
    print(f"  2. Define {name}Props with semantic prop names (not 'data', 'value', 'type')")
    print(f"  3. Implement {name}Ready — the nominal state only")
    print(f"  4. Complete Psychological Load Audit before merge")
    print(f"  5. Ensure all metric values use fontData token (IBM Plex Mono)")

def main():
    parser = argparse.ArgumentParser(description='Generate Skeldir React/TypeScript component')
    parser.add_argument('name', help='Component name (PascalCase, e.g., MetricCard)')
    parser.add_argument('--type', choices=COMPONENT_TYPES, default='card', help='Component type')
    parser.add_argument('--output', default='src/components', help='Output directory')

    args = parser.parse_args()

    if not args.name[0].isupper():
        print(f"Error: Component name must be PascalCase (e.g., '{args.name.capitalize()}')")
        sys.exit(1)

    generate_component(args.name, args.type, args.output)

if __name__ == '__main__':
    main()
