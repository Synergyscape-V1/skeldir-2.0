# D0 Token Naming Governance

**Document**: Design System Token Naming Convention & Extension Rules
**Status**: AUTHORITATIVE - Enforced by CI
**Date**: February 2, 2026
**Version**: 1.0

---

## 1. PURPOSE

This document defines:

1. **Closed-world token naming convention** - How tokens are named by semantic category
2. **Validation rules** - How to check conformance
3. **Extension mechanism** - How to propose new semantic categories
4. **Realistic examples** - Real scenarios showing the naming scheme in action

Enforced by: ESLint rules + `validate-tokens.js` script in CI pipeline.

---

## 2. CORE PRINCIPLE: SEMANTIC CATEGORIES

### 2.1 Why Semantic, Not Arbitrary?

**Bad naming** (causes confusion):
```
--color-1, --color-2, --color-3         # What do they mean?
--size-big, --size-medium, --size-huge  # Relative to what?
--spacing-foo, --spacing-bar            # No semantic meaning
```

**Good naming** (semantic):
```
--color-primary, --color-success, --color-error  # Purpose is clear
--space-sm, --space-md, --space-lg               # Consistent scale
--shadow-md, --shadow-lg                        # Intensity is obvious
```

**Skeldir's approach**: Every token name communicates its **semantic purpose** (what it's for) and optionally its **variation** (size, state, etc.).

---

## 3. SEMANTIC CATEGORIES & NAMING PATTERNS

### 3.1 Colors: `--color-{semantic}-{variant}`

**Closed-World Semantic Categories**:

| Category | Usage | Examples |
|----------|-------|----------|
| **primary** | Main brand color, primary actions | `--color-primary`, `--color-primary-hover` |
| **success** | Success states, positive affirmation | `--color-success`, `--color-success-light` |
| **warning** | Warning states, caution, attention | `--color-warning`, `--color-warning-light` |
| **error** | Error states, failure, destructive | `--color-error`, `--color-error-light` |
| **info** | Informational states, neutral data | `--color-info`, `--color-info-light` |
| **confidence-high** | Skeldir-specific: high confidence indicator | `--color-confidence-high` |
| **confidence-medium** | Skeldir-specific: medium confidence | `--color-confidence-medium` |
| **confidence-low** | Skeldir-specific: low confidence | `--color-confidence-low` |
| **neutral** | Neutral color (grays), no semantic meaning | `--color-neutral-dark`, `--color-neutral-light` |

**Variant Options**:
- `-light` (lighter shade for backgrounds)
- `-dark` (darker shade for text/borders)
- `-hover` (interactive state)
- `-active` (pressed/selected state)
- `-disabled` (disabled state)
- `-bg` (background-specific variant)
- `-text` (text-specific variant)

**Examples**:
```css
--color-primary: #3B82F6;           /* Primary brand blue */
--color-primary-hover: #2563EB;     /* Darker on hover */
--color-primary-active: #1D4ED8;    /* Even darker when pressed */
--color-primary-light: #DBEAFE;     /* Light background */

--color-success: #10B981;           /* Success green */
--color-success-light: #D1FAE5;     /* Light success background */

--color-confidence-high: #10B981;   /* Maps to success color */
--color-confidence-medium: #F59E0B; /* Maps to warning color */
--color-confidence-low: #EF4444;    /* Maps to error color */
```

**Constraint**: Cannot invent new color semantic categories without amendment to this document.

---

### 3.2 Spacing: `--space-{size}`

**Scale**: 8-point grid (4px base unit)

| Token | Value | Use Case |
|-------|-------|----------|
| `--space-1` | 4px | Tight inline spacing, micro UI |
| `--space-2` | 8px | Compact spacing between elements |
| `--space-3` | 12px | Small spacing |
| `--space-4` | 16px | Standard spacing (most common) |
| `--space-5` | 20px | Medium spacing |
| `--space-6` | 24px | Larger spacing between components |
| `--space-8` | 32px | Section-level spacing |
| `--space-10` | 40px | Major section breaks |
| `--space-12` | 48px | Page-level divisions |
| `--space-16` | 64px | Full page sections |
| `--space-20` | 80px | Major page breaks |

**Usage**:
```css
padding: var(--space-4);        /* Standard padding */
margin-bottom: var(--space-6);  /* Component spacing */
gap: var(--space-2);            /* Flex/grid gaps */
```

**Constraint**: Spacing scale is fixed (cannot add arbitrary values like `--space-7` without governance change).

---

### 3.3 Typography: `--font-{property}-{variant}`

**Font Families**:
```css
--font-family-display: "Plus Jakarta Sans", system-ui, sans-serif;
--font-family-body: "Inter", system-ui, sans-serif;
```

**Named Text Styles** (use these, not raw font-size values):

| Token | Size | Weight | Line-height | Use Case |
|-------|------|--------|-------------|----------|
| `--text-display-lg` | 48px | 600 | 1.2 | Page title |
| `--text-display-md` | 36px | 600 | 1.3 | Section header |
| `--text-heading-lg` | 24px | 600 | 1.4 | Card title |
| `--text-heading-md` | 20px | 600 | 1.4 | Subsection |
| `--text-heading-sm` | 16px | 600 | 1.5 | Label, emphasis |
| `--text-body-lg` | 16px | 400 | 1.6 | Primary body text |
| `--text-body-md` | 14px | 400 | 1.5 | Secondary body |
| `--text-body-sm` | 12px | 400 | 1.4 | Metadata, caption |
| `--text-label-lg` | 14px | 500 | 1.4 | Form label |
| `--text-label-md` | 12px | 500 | 1.4 | Small label |
| `--text-mono` | 14px | 400 | 1.5 | Code, data |

**Usage** (in CSS):
```css
.heading {
  font-family: var(--font-family-display);
  font-size: 36px;
  font-weight: 600;
  line-height: 1.3;
}
```

**Usage** (in Tailwind, after token extension):
```html
<h1 class="text-display-md">Page Title</h1>
<p class="text-body-lg">Body text</p>
```

**Constraint**: Cannot invent new text style sizes; must fit into this 11-token hierarchy.

---

### 3.4 Effects: `--{effect-type}-{intensity}`

**Shadows**:
```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
--shadow-md: 0 4px 6px rgba(0,0,0,0.07);
--shadow-lg: 0 10px 15px rgba(0,0,0,0.10);
--shadow-xl: 0 20px 25px rgba(0,0,0,0.15);
--shadow-focus: 0 0 0 3px rgba(59,130,246,0.3);  /* Focus ring */
```

**Border Radius**:
```css
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-xl: 16px;
--radius-full: 9999px;  /* Pill shape */
```

**Animation Duration**:
```css
--duration-fast: 150ms;
--duration-normal: 250ms;
--duration-slow: 400ms;
```

**Easing Functions**:
```css
--ease-default: cubic-bezier(0.4, 0, 0.2, 1);
--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
```

**Constraint**: New effects must fit into these categories; cannot invent arbitrary easing values.

---

## 4. VALIDATION RULES

### 4.1 Pattern Matching (Enforced by ESLint)

**All color tokens must match**:
```regex
^--color-[a-z]+-([a-z-])*$
```

**Valid examples**:
- `--color-primary` ✓
- `--color-primary-hover` ✓
- `--color-success-light` ✓
- `--color-confidence-high` ✓

**Invalid examples**:
- `--color-1` ✗ (not semantic)
- `--color-myCustomColor` ✗ (camelCase not allowed)
- `--color-primary_hover` ✗ (underscore not allowed)
- `--color-arbitrary-new-thing` ✗ (not in semantic categories)

**All spacing tokens must match**:
```regex
^--space-[0-9]+$
```

**Valid examples**:
- `--space-1` ✓
- `--space-4` ✓
- `--space-20` ✓

**Invalid examples**:
- `--space-sm` ✗ (use number, not name)
- `--space-custom` ✗ (arbitrary values not allowed)

**All typography tokens must match**:
```regex
^--(?:font-family|text-)[a-z]+(?:-[a-z]+)?$
```

**Valid examples**:
- `--font-family-display` ✓
- `--text-body-lg` ✓
- `--text-label-md` ✓

**All effect tokens must match**:
```regex
^--(?:shadow|radius|duration|ease)-[a-z-]+$
```

**Valid examples**:
- `--shadow-md` ✓
- `--radius-lg` ✓
- `--duration-slow` ✓

---

### 4.2 Forbidden Patterns (Enforced by ESLint + validate-tokens.js)

**Raw hex values**:
```css
color: #3B82F6;           /* ✗ FORBIDDEN - use var(--color-primary) */
background: #FFFFFF;      /* ✗ FORBIDDEN - use var(--color-background) */
```

**Raw pixel values** (for spacing, sizing):
```css
margin: 16px;             /* ✗ FORBIDDEN - use var(--space-4) */
padding: 24px;            /* ✗ FORBIDDEN - use var(--space-6) */
border-radius: 8px;       /* ✗ FORBIDDEN - use var(--radius-md) */
```

**Raw font sizes** (after typography locked):
```css
font-size: 16px;          /* ✗ FORBIDDEN - use var(--text-body-lg) */
line-height: 1.6;         /* ✗ FORBIDDEN - should be built into text style */
```

**Magic numbers**:
```css
animation-duration: 250ms;   /* ✗ FORBIDDEN - use var(--duration-normal) */
box-shadow: 0 4px 6px ...;   /* ✗ FORBIDDEN - use var(--shadow-md) */
```

**Exception process**: See Section 5 (Extension Mechanism)

---

## 5. EXTENSION MECHANISM

### 5.1 When to Propose a New Token

**DO propose new tokens when**:
1. A design need doesn't fit existing tokens
2. It's a **recurring pattern** (at least 3 use cases)
3. You can articulate the semantic purpose clearly

**DON'T propose new tokens when**:
1. It's a one-off exception (use existing token instead)
2. You can't explain why existing tokens don't work
3. It creates naming collision or confusion

### 5.2 Extension Process

**Step 1: Document the Gap**

Create an issue to `docs/design/` with:
```
Title: "Design System: New token needed - {semantic category}"

Description:
- What component/pattern needs this token?
- Why don't existing tokens work?
- How many places will use this token? (≥3)
- Proposed token name: --{category}-{name}
- Proposed value: (hex for color, pixel for spacing, etc.)
```

**Step 2: Validate Naming**

Check against this governance doc:
- Does it fit an existing semantic category?
- If new category, does it follow the pattern?
- No naming collisions with existing tokens?

**Step 3: Technical Review**

Design + Engineering leads assess:
- Is this truly unavoidable?
- Does it violate WCAG AA (for colors)?
- Will it set a bad precedent?

**Step 4: Amendment (if approved)**

Update this document with new category or token, then:
1. Update `src/index.css` (add CSS variable)
2. Update `tailwind.config.js` (map token if Tailwind utility)
3. Update `.eslintrc.json` (allow new pattern in linting)
4. Update validation script (recognize new token)
5. Merge with design + engineering sign-off

---

### 5.3 Example: Extending for Centaur Workflow States

**Scenario**: Skeldir's Centaur LLM workflow has states (processing/pending/validating) not in standard design systems.

**Issue Document**:
```
Title: "New token needed - Centaur workflow state colors"

Reason:
- Command Center shows "Processing..." state during model training
- Budget Optimizer shows "Analyzing..." during optimization
- Investigation Queue shows "Thinking..." during AI analysis
- Current color tokens (success/warning/error) don't semantically fit "processing"

Proposed Extension:
- New semantic category: "state" (for workflow/progress states)
- Pattern: --color-state-{name}
- Initial tokens:
  --color-state-processing: #3B82F6 (blue, indicating activity)
  --color-state-pending: #F59E0B (yellow, indicating wait)
  --color-state-validating: #8B5CF6 (purple, indicating verification)

WCAG AA Validation:
- All states tested against white background
- Ratios: 4.8:1 (exceeds 4.5:1 requirement)

Precedent:
- Does not conflict with existing colors
- Creates new semantic category (valid extension)
- Applies to Skeldir's unique Centaur model
```

**Review Outcome** (hypothetical):
- ✓ Approved - Fills clear gap
- ✓ Naming is unambiguous
- ✓ Contrast validated
- ✓ Precedent is healthy (Skeldir-specific extension)

**Amendment**:
- Add to `D0_TOKEN_NAMING_GOVERNANCE.md` Section 3.1
- Create tokens in `src/index.css`
- Merge PR with sign-offs

---

## 6. GOVERNANCE CHECKLIST FOR NEW TOKENS

Use this before proposing:

**Semantic Justification**:
- [ ] Token has a clear, non-arbitrary semantic meaning
- [ ] 3+ use cases exist (not a one-off)
- [ ] Existing tokens were evaluated and found insufficient
- [ ] Name clearly communicates purpose

**Naming Validation**:
- [ ] Follows pattern for its category (color, spacing, etc.)
- [ ] No camelCase, underscores, or other non-standard characters
- [ ] No collision with existing token names
- [ ] Variant suffix (if any) is from standard list (-light, -dark, -hover, etc.)

**Technical Validation** (for colors):
- [ ] Contrast tested against light and dark backgrounds
- [ ] WCAG AA requirements met (4.5:1 body, 3:1 large text)
- [ ] Accessible with and without color alone (icon or other indicator included)

**Documentation**:
- [ ] Update to `D0_TOKEN_NAMING_GOVERNANCE.md` prepared
- [ ] Example use case documented
- [ ] CSS variable value specified
- [ ] Tailwind config mapping (if applicable) specified

**Approval**:
- [ ] Design lead sign-off
- [ ] Engineering lead sign-off
- [ ] No breaking changes to existing tokens

---

## 7. CURRENT TOKEN INVENTORY

### 7.1 Colors (Planned: 47 tokens)

**Status**: Awaiting D0-P4 (Color System) implementation

**Will include**:
- 6 backgrounds
- 5 text colors
- 8 status colors
- 6 confidence colors (Skeldir-specific)
- 6 data visualization colors
- 8 interactive colors
- 2 border colors

### 7.2 Spacing (Planned: 12 tokens)

**Status**: Awaiting D0-P1 (Token Architecture) implementation

**Will include**:
- `--space-1` through `--space-20` (8-point scale)
- 12 total values

### 7.3 Typography (Planned: 11 named styles + 2 families)

**Status**: Awaiting D0-P3 (Typography) implementation

**Will include**:
- 11 text styles (display, heading, body, label, mono)
- 2 font families (display, body)

### 7.4 Effects (Planned: 19 tokens)

**Status**: Awaiting D0-P0 completion

**Will include**:
- 5 shadows
- 5 border radius
- 5 animation durations
- 4 easing functions

---

## 8. VALIDATION CHECKLIST TEMPLATE

Use this format to validate token names before committing:

```markdown
## Token Validation Checklist

- [ ] All color tokens match pattern: `^--color-[a-z]+(-[a-z]+)?$`
- [ ] All spacing tokens match pattern: `^--space-[0-9]+$`
- [ ] All typography tokens match pattern: `^--(?:font-family|text-)[a-z-]+$`
- [ ] All effect tokens match pattern: `^--(?:shadow|radius|duration|ease)-[a-z-]+$`
- [ ] No raw hex values in CSS (use var(--color-*))
- [ ] No raw pixel values for spacing (use var(--space-*))
- [ ] No raw font sizes (use var(--text-*))
- [ ] ESLint passes: `npm run lint`
- [ ] Token validation passes: `npm run validate-tokens`
- [ ] No tokens break WCAG AA contrast
```

---

## 9. RELATED DOCUMENTS

- `D0_PHASE_CONTRACT.md` - References this governance doc, Section 3.3
- `docs/forensics/D0_P0_EVIDENCE.md` - Hypothesis H03 test demonstrates naming extensibility
- `frontend/.eslintrc.json` - ESLint rules enforce patterns
- `frontend/scripts/validate-tokens.js` - Automated validation

---

## 10. QUICK REFERENCE

### Color Pattern
```
--color-{semantic}-{variant}
Examples: --color-primary, --color-success-light, --color-confidence-high
Constraint: Semantic must be in approved list; variant is optional
```

### Spacing Pattern
```
--space-{number}
Examples: --space-1, --space-4, --space-16
Constraint: Number must be 1-20 on 4px scale
```

### Typography Pattern
```
--font-family-{name} or --text-{style}-{size}
Examples: --font-family-body, --text-body-lg, --text-label-md
Constraint: Style and size must match approved hierarchy
```

### Effects Pattern
```
--{type}-{intensity}
Examples: --shadow-md, --radius-lg, --duration-slow, --ease-out
Constraint: Type and intensity must match approved effects
```

---

## DOCUMENT HISTORY

| Version | Date | Change | Status |
|---------|------|--------|--------|
| 1.0 | Feb 2, 2026 | Initial governance rules | ACTIVE |

---

*D0 Token Naming Governance v1.0*
*Enforced by ESLint and validate-tokens.js in CI pipeline*
