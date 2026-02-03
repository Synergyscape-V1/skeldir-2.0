# Skeldir Design System Token Taxonomy Reference

**Document**: Canonical Token Taxonomy for D0-P1
**Version**: 1.0
**Date**: 2026-02-03
**Status**: AUTHORITATIVE - Reference for JSON exports

---

## Purpose

This document defines the **complete, canonical taxonomy** of design tokens for Skeldir's design system foundation (D0-P1). This taxonomy is the single source of truth for:

- JSON token exports (`skeldir-tokens-*.json`)
- CSS variable scaffolding (`src/index.css`)
- Tailwind configuration (`tailwind.config.js`)
- Validation scripts (`scripts/validate-tokens.js`)

**Total Token Count**: 91 tokens
- Colors: 47 tokens
- Spacing: 12 tokens
- Typography: 13 tokens (11 text styles + 2 font families)
- Effects: 19 tokens (5 shadows + 6 radii + 5 durations + 3 easings)

---

## 1. Color Tokens (47 total)

### 1.1 Background (6 tokens)

| Token Name | Purpose | Usage |
|------------|---------|-------|
| `--color-background` | Primary background color | Main page background |
| `--color-background-muted` | Muted background variant | Subtle backgrounds, disabled states |
| `--color-background-card` | Card background | Cards, panels, elevated surfaces |
| `--color-background-popover` | Popover background | Dropdowns, tooltips, modals |
| `--color-background-sidebar` | Sidebar background | Navigation sidebar |
| `--color-background-accent` | Accent background | Highlighted or selected areas |

### 1.2 Text (5 tokens)

| Token Name | Purpose | Usage |
|------------|---------|-------|
| `--color-text-primary` | Primary text color | Body text, headings |
| `--color-text-secondary` | Secondary text color | Supporting text, labels |
| `--color-text-muted` | Muted text color | Placeholder, disabled, metadata |
| `--color-text-disabled` | Disabled text color | Disabled form inputs, inactive elements |
| `--color-text-inverse` | Inverse text color | Text on dark backgrounds |

### 1.3 Status (8 tokens)

| Token Name | Purpose | Usage |
|------------|---------|-------|
| `--color-success` | Success indicator | Success states, positive affirmation |
| `--color-success-light` | Success background | Light success backgrounds |
| `--color-warning` | Warning indicator | Warning states, caution |
| `--color-warning-light` | Warning background | Light warning backgrounds |
| `--color-error` | Error indicator | Error states, destructive actions |
| `--color-error-light` | Error background | Light error backgrounds |
| `--color-info` | Info indicator | Informational states, neutral data |
| `--color-info-light` | Info background | Light info backgrounds |

### 1.4 Confidence (6 tokens - Skeldir-Specific)

| Token Name | Purpose | Usage |
|------------|---------|-------|
| `--color-confidence-high` | High confidence indicator | AI/ML high confidence scores (>80%) |
| `--color-confidence-high-bg` | High confidence background | Badges, backgrounds for high confidence |
| `--color-confidence-medium` | Medium confidence indicator | AI/ML medium confidence scores (50-80%) |
| `--color-confidence-medium-bg` | Medium confidence background | Badges, backgrounds for medium confidence |
| `--color-confidence-low` | Low confidence indicator | AI/ML low confidence scores (<50%) |
| `--color-confidence-low-bg` | Low confidence background | Badges, backgrounds for low confidence |

### 1.5 Data Visualization (6 tokens)

| Token Name | Purpose | Usage |
|------------|---------|-------|
| `--color-chart-1` | Chart color 1 | First data series in charts |
| `--color-chart-2` | Chart color 2 | Second data series in charts |
| `--color-chart-3` | Chart color 3 | Third data series in charts |
| `--color-chart-4` | Chart color 4 | Fourth data series in charts |
| `--color-chart-5` | Chart color 5 | Fifth data series in charts |
| `--color-chart-6` | Chart color 6 | Sixth data series in charts |

### 1.6 Interactive (14 tokens)

| Token Name | Purpose | Usage |
|------------|---------|-------|
| `--color-primary` | Primary action color | Primary buttons, links, brand color |
| `--color-primary-hover` | Primary hover state | Hover state for primary elements |
| `--color-primary-active` | Primary active state | Active/pressed state for primary elements |
| `--color-primary-disabled` | Primary disabled state | Disabled primary elements |
| `--color-primary-foreground` | Text on primary | Text color on primary backgrounds |
| `--color-secondary` | Secondary action color | Secondary buttons, less prominent actions |
| `--color-secondary-hover` | Secondary hover state | Hover state for secondary elements |
| `--color-secondary-disabled` | Secondary disabled state | Disabled secondary elements |
| `--color-secondary-foreground` | Text on secondary | Text color on secondary backgrounds |
| `--color-destructive` | Destructive action color | Delete, remove, destructive actions |
| `--color-destructive-hover` | Destructive hover state | Hover state for destructive actions |
| `--color-destructive-foreground` | Text on destructive | Text color on destructive backgrounds |
| `--color-link` | Link color | Hyperlinks, text links |
| `--color-link-hover` | Link hover state | Hover state for links |

### 1.7 Border (2 tokens)

| Token Name | Purpose | Usage |
|------------|---------|-------|
| `--color-border` | Primary border color | Borders, dividers, separators |
| `--color-border-muted` | Muted border color | Subtle borders, less prominent dividers |

---

## 2. Spacing Tokens (12 total)

**Scale**: 8-point grid (4px base unit)

| Token Name | Value | Rem | Usage |
|------------|-------|-----|-------|
| `--space-1` | 4px | 0.25rem | Tight inline spacing, micro UI |
| `--space-2` | 8px | 0.5rem | Compact spacing between elements |
| `--space-3` | 12px | 0.75rem | Small spacing |
| `--space-4` | 16px | 1rem | Standard spacing (most common) |
| `--space-5` | 20px | 1.25rem | Medium spacing |
| `--space-6` | 24px | 1.5rem | Larger spacing between components |
| `--space-8` | 32px | 2rem | Section-level spacing |
| `--space-10` | 40px | 2.5rem | Major section breaks |
| `--space-12` | 48px | 3rem | Page-level divisions |
| `--space-16` | 64px | 4rem | Full page sections |
| `--space-20` | 80px | 5rem | Major page breaks |
| `--space-24` | 96px | 6rem | Largest spacing value |

**Usage Notes**:
- Default padding/margin: `--space-4`
- Card padding: `--space-6`
- Section spacing: `--space-8` or `--space-10`
- Page margins: `--space-12` or larger

---

## 3. Typography Tokens (13 total)

### 3.1 Font Families (2 tokens)

| Token Name | Value | Usage |
|------------|-------|-------|
| `--font-family-display` | "Plus Jakarta Sans", system-ui, sans-serif | Headings, display text, emphasis |
| `--font-family-body` | "Inter", system-ui, sans-serif | Body text, UI elements, labels |

### 3.2 Text Styles (11 tokens)

| Token Name | Size | Weight | Line Height | Usage |
|------------|------|--------|-------------|-------|
| `--text-display-lg` | 48px | 600 | 1.2 | Page title, hero headings |
| `--text-display-md` | 36px | 600 | 1.3 | Section header, major headings |
| `--text-heading-lg` | 24px | 600 | 1.4 | Card title, subsection header |
| `--text-heading-md` | 20px | 600 | 1.4 | Subsection, card header |
| `--text-heading-sm` | 16px | 600 | 1.5 | Label emphasis, small heading |
| `--text-body-lg` | 16px | 400 | 1.6 | Primary body text, main content |
| `--text-body-md` | 14px | 400 | 1.5 | Secondary body text, UI text |
| `--text-body-sm` | 12px | 400 | 1.4 | Metadata, caption, small text |
| `--text-label-lg` | 14px | 500 | 1.4 | Form label, button text |
| `--text-label-md` | 12px | 500 | 1.4 | Small label, input label |
| `--text-mono` | 14px | 400 | 1.5 | Code, data, monospace text |

**Usage Notes**:
- Text styles include size, weight, and line-height
- Always use text styles instead of raw font-size values
- Display styles use display font family
- Body and label styles use body font family
- Mono style uses monospace fallback

---

## 4. Effects Tokens (19 total)

### 4.1 Shadows (5 tokens)

| Token Name | Value | Usage |
|------------|-------|-------|
| `--shadow-sm` | 0 1px 2px rgba(0,0,0,0.05) | Subtle elevation, hover states |
| `--shadow-md` | 0 4px 6px rgba(0,0,0,0.07) | Standard card shadow |
| `--shadow-lg` | 0 10px 15px rgba(0,0,0,0.10) | Elevated cards, modals |
| `--shadow-xl` | 0 20px 25px rgba(0,0,0,0.15) | High elevation, dialogs |
| `--shadow-focus` | 0 0 0 3px rgba(59,130,246,0.3) | Focus ring for accessibility |

### 4.2 Border Radius (6 tokens)

| Token Name | Value | Usage |
|------------|-------|-------|
| `--radius-none` | 0 | No rounding (square corners) |
| `--radius-sm` | 4px | Subtle rounding, small elements |
| `--radius-md` | 8px | Standard rounding (most common) |
| `--radius-lg` | 12px | Larger rounding, cards |
| `--radius-xl` | 16px | Very rounded corners |
| `--radius-full` | 9999px | Fully rounded (pills, circles) |

### 4.3 Animation Duration (5 tokens)

| Token Name | Value | Usage |
|------------|-------|-------|
| `--duration-instant` | 100ms | Immediate feedback, micro-interactions |
| `--duration-fast` | 150ms | Quick transitions |
| `--duration-normal` | 250ms | Standard animation speed (most common) |
| `--duration-slow` | 400ms | Deliberate transitions, modals |
| `--duration-slower` | 600ms | Slow animations, page transitions |

### 4.4 Easing Functions (3 tokens)

| Token Name | Value | Usage |
|------------|-------|-------|
| `--ease-default` | cubic-bezier(0.4, 0, 0.2, 1) | Default easing (standard ease-in-out) |
| `--ease-in` | cubic-bezier(0.4, 0, 1, 1) | Ease-in (accelerating) |
| `--ease-out` | cubic-bezier(0, 0, 0.2, 1) | Ease-out (decelerating) |

---

## State Model Coverage

The token taxonomy covers the following interaction states where applicable:

- **Default**: Base state (all tokens)
- **Hover**: Interactive elements (`-hover` variant)
- **Active**: Pressed/selected state (`-active` variant)
- **Disabled**: Inactive/disabled state (`-disabled` variant)
- **Focus**: Keyboard focus (via `--shadow-focus`)

Not all tokens require all states. Guidance:
- Background tokens: No state variants needed
- Text tokens: Only disabled variant needed
- Interactive tokens: Hover, active, disabled variants required
- Status tokens: Light background variants for contrast

---

## WCAG AA Compliance

All color token pairs MUST pass WCAG AA contrast requirements:

- **Body text** (14px, normal): 4.5:1 minimum
- **Large text** (18px+ or 14px bold+): 3:1 minimum
- **Interactive elements**: 3:1 minimum

**Enforcement**: Contrast validation via `scripts/validate-contrast.mjs` is required before token export.

---

## Engineer Handoff Checklist

Use this checklist to verify token implementation:

- [ ] All 91 tokens defined in JSON exports
- [ ] All tokens mapped to CSS variables in `src/index.css`
- [ ] All tokens mapped to Tailwind config where applicable
- [ ] Token naming follows D0 governance (`--color-*`, `--space-*`, etc.)
- [ ] Contrast validation passes for all color pairs
- [ ] No raw hex, pixel, or font-size values in code (except in token definitions)
- [ ] Validation scripts pass with exit code 0

---

## Related Documents

- **D0_PHASE_CONTRACT.md**: Architectural constraints and integration points
- **D0_TOKEN_NAMING_GOVERNANCE.md**: Naming rules and extension mechanism
- **D0_P1_VALIDATION_FINDINGS.md**: Empirical evidence for this taxonomy

---

**Document Status**: READY FOR IMPLEMENTATION
**Approved**: Engineering can scaffold from this taxonomy
**Next Action**: Create JSON exports (R-A02)
