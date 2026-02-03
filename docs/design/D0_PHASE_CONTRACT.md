# D0 Phase Contract: Design Foundation Infrastructure

**Document**: Skeldir Design Foundation Phase Lock
**Status**: AUTHORITATIVE - Governs all downstream design phases
**Date Locked**: February 2, 2026
**Next Review**: Upon completion of D0-P5 (Color System) or if architectural conflicts arise

---

## 1. CONTRACT METADATA

### 1.1 Purpose

This document establishes the **single canonical contract** for Skeldir's design system foundation (D0 phase). It locks:

- **Environmental constraints** (where tokens live, how they're consumed)
- **Architectural decisions** (Tailwind + CSS variables, Tailwind defaults for breakpoints)
- **Naming conventions** (semantic categories, extension rules)
- **Integration points** (file paths, import chains)
- **Validation gates** (exit criteria for each sub-phase)

### 1.2 Governance

**Authority**: This contract overrides:
- `SCAFFOLD.md` (which describes current state, not design decisions)
- Earlier phase plans (which are aspirational until locked here)
- Ambiguous architectural discussions

**This document does NOT override**:
- Engineering implementation constraints (tool requirements, build system changes)
- Security and compliance requirements
- Accessibility regulations (WCAG AA is upstream)

### 1.3 Change Protocol

**Who can propose changes**: Any team member via GitHub issue to `docs/design/`

**How**: Create issue with tag `design-system-contract-change`, include:
1. What in the contract is unclear or blocking
2. Proposed change with justification
3. Impact on downstream phases (D1, D2, etc.)

**Who approves**: Design + Engineering leads (TBD: define CODEOWNERS rule)

**When merged**: Change must include evidence of impact assessment on all downstream phases

---

## 2. ENVIRONMENTAL ANCHORING

### 2.1 Styling System Decision: Tailwind CSS + CSS Custom Properties

**Decision**: Skeldir will use **Tailwind CSS utility-first framework** with **CSS custom properties** for design tokens.

**Rationale**:
- Tailwind is already configured and in use (`tailwind.config.js` exists)
- Utility-first reduces CSS bloat and enforces consistency
- CSS custom properties provide a theming layer (dark mode, future A/B testing)
- Reduces coupling between component CSS and token values

**Constraints**:
- All styling must derive from design tokens or Tailwind utilities
- No raw hex values, pixel values, or magic numbers in code after D0 lock
- Custom CSS should be minimal; prefer Tailwind `@apply` for component styles

**File Structure**:
```
frontend/
├── src/
│   ├── index.css          # Entry point for all styles
│   ├── main.tsx           # App entry, imports index.css
│   └── (components)
├── tailwind.config.js     # Tailwind configuration
├── postcss.config.js      # PostCSS plugins (tailwind + autoprefixer)
└── tsconfig.json          # TypeScript configuration

docs/design/
├── D0_PHASE_CONTRACT.md   # This document
├── D0_TOKEN_NAMING_GOVERNANCE.md
├── tokens/
│   ├── skeldir-tokens-color.json
│   ├── skeldir-tokens-spacing.json
│   ├── skeldir-tokens-typography.json
│   └── skeldir-tokens-effects.json
└── evidence/
    └── docs/forensics/D0_P0_EVIDENCE.md
```

---

### 2.2 CSS Variables Integration Point

**Where tokens live**: CSS custom properties in `src/index.css`

**Structure**:
```css
/* src/index.css */

/* Layer 1: CSS Custom Properties (Design Tokens) */
:root {
  /* Color tokens */
  --color-primary: #3B82F6;
  --color-success: #10B981;
  /* ... etc (47 colors total from D0-P4) */

  /* Spacing tokens */
  --space-1: 4px;
  --space-2: 8px;
  /* ... etc (12 spacing values total from D0-P1) */

  /* Typography tokens */
  --font-family-display: "Plus Jakarta Sans", system-ui, sans-serif;
  --font-family-body: "Inter", system-ui, sans-serif;
  --font-size-body-lg: 16px;
  /* ... etc (11 typography tokens from D0-P3) */

  /* Effect tokens */
  --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
  --radius-md: 8px;
  --duration-normal: 250ms;
  /* ... etc (19 effect tokens from D0-P0) */
}

/* Layer 2: Tailwind Layers */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Layer 3: Global Custom CSS (future, if needed) */
/* Reserved for post-token-lock customization */
```

**Import Chain** (verified working):
```
index.html
  → <script type="module" src="/src/main.tsx">
    → main.tsx (line 3): import "./index.css"
      → PostCSS processes @tailwind directives
      → Tailwind scans src/**/*.{js,ts,jsx,tsx} for classes
      → Generates CSS for used classes
      → CSS variables are injected at :root scope
      → Vite includes in dev HMR or production bundle
```

**Consumption Pattern** (in components):
```typescript
// Button component example
export function Button({ variant = "primary" }) {
  const bgColorVar = `var(--color-${variant})`;
  return (
    <button style={{ backgroundColor: bgColorVar }}>
      Click me
    </button>
  );
}
```

---

### 2.3 Tailwind Configuration Constraints

**What is locked**:
- `content` glob: `["./index.html", "./src/**/*.{js,ts,jsx,tsx}"]` (must remain)
- `theme.extend` usage: Must populate with Tailwind config equivalents of design tokens
- PostCSS pipeline: Tailwind must run before component compilation

**What is NOT locked**:
- Specific breakpoint values (will be defined in D0-P2 Grid System)
- Color values (will be defined in D0-P4)
- Spacing scale values (will be defined in D0-P1)

**Configuration Precedence**:
1. **Design tokens (CSS variables)** - Source of truth for values
2. **Tailwind `theme.extend`** - Maps to design tokens or Tailwind defaults
3. **Tailwind defaults** - Used only where tokens don't override

**Example** (after tokens are defined):
```javascript
// tailwind.config.js (after D0-P1 through D0-P4 complete)
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "var(--color-primary)",
        success: "var(--color-success)",
        // ... 45 more color tokens
      },
      spacing: {
        1: "var(--space-1)",
        2: "var(--space-2)",
        // ... 10 more spacing tokens
      },
      // fontSize, fontFamily, etc.
    },
  },
  plugins: [],
}
```

---

## 3. NON-NEGOTIABLE INVARIANTS

These rules are **enforced by CI and cannot be overridden**:

### 3.1 No Raw Values After D0 Lock

**Rule**: After D0-P4 completion, zero raw hex, pixel, or dimension values in code.

**Enforcement**:
- `npm run lint` checks for hardcoded colors (pattern: `#[0-9a-f]{3,6}`)
- `validate-tokens.js` scans CSS and config files
- CI gates merge if violations found

**Exception process**:
1. Document the exception in `docs/design/EXCEPTIONS.md`
2. Provide rationale (why token is insufficient)
3. Propose new token to cover the case
4. Get approval from design + engineering leads
5. Add the token to D0 contract before merging

### 3.2 Contrast Validation Upstream

**Rule**: All color pairs must pass WCAG AA before export.

**Validation Gate** (D0-P4 exit):
- All text/background pairs: 4.5:1 minimum (body text)
- All large text pairs: 3:1 minimum (18pt+ or 14pt bold+)
- All interactive elements: 3:1 minimum (icon/button on background)

**Process**:
1. Define color tokens in Figma
2. Run contrast checker on all pairs
3. Document in `skeldir-color-contrast-matrix.md`
4. Export tokens ONLY after all pairs pass
5. CI blocks merge if contrast fails

**Rationale**: Fixing contrast AFTER export would invalidate component implementations and break the D0 contract.

### 3.3 Token Naming Governance

**Rule**: All tokens must follow semantic naming convention defined in `D0_TOKEN_NAMING_GOVERNANCE.md`.

**Closed-World Semantic Categories**:
- Colors: `--color-{semantic}-{variant}`
- Spacing: `--space-{size}`
- Typography: `--font-{property}-{variant}`
- Effects: `--{effect-type}-{intensity}`

**Enforcement**:
- `validate-tokens.js` checks naming patterns
- CI rejects PRs with non-conformant token names
- Extension process required for new semantic categories

**See**: `D0_TOKEN_NAMING_GOVERNANCE.md` for full rules

### 3.4 Accessibility as Upstream Constraint

**Rule**: Accessibility (WCAG AA) is NOT validation-last; it's validation-first.

**Application**:
- D0-P4 (Color System) validates contrast before lock
- D1 (Atomic Components) validates focus states and semantics
- All phases include accessibility audit as exit gate

**Non-negotiable checks**:
- ✓ Contrast ratios on all color pairs
- ✓ Focus state visibility on all interactive elements
- ✓ Semantic HTML and ARIA attributes (engineering phase)
- ✓ Color is never the only indicator (use icon + color)

---

## 4. REPOSITORY STRUCTURE & FILE LOCATIONS

### 4.1 Design System Home Directory

**Root**: `docs/design/`

**Purpose**: All design documentation, specifications, and exports live here

**Structure**:
```
docs/design/
│
├── D0_PHASE_CONTRACT.md                    # This document (entry point)
├── D0_TOKEN_NAMING_GOVERNANCE.md          # Naming rules and extensions
│
├── evidence/
│   └── docs/forensics/D0_P0_EVIDENCE.md                  # Investigation findings & validation
│
├── tokens/
│   ├── skeldir-tokens-color.json          # 47 color tokens (D0-P4 output)
│   ├── skeldir-tokens-spacing.json        # 12 spacing tokens (D0-P1 output)
│   ├── skeldir-tokens-typography.json     # 11 typography tokens (D0-P3 output)
│   ├── skeldir-tokens-effects.json        # 19 effect tokens (D0-P0 output)
│   └── skeldir-color-contrast-matrix.md   # WCAG validation proof (D0-P4)
│
├── specifications/
│   ├── D0_P0_TOKEN_ARCHITECTURE.md        # Token definitions (design spec)
│   ├── D0_P1_GRID_SPECIFICATION.md        # Grid system spec
│   ├── D0_P2_TYPOGRAPHY_GUIDE.md          # Typography usage guide
│   ├── D0_P3_COLOR_GUIDE.md               # Color usage guide + contrast matrix
│   └── (D1, D2, D3 specifications in later phases)
│
├── templates/
│   ├── token-specimen-template.html       # Non-layout demo template
│   └── component-spec-template.md         # Component spec format
│
└── EXCEPTIONS.md                          # Approved deviations from contract
```

### 4.2 Frontend Source Integration

**CSS Entry**: `frontend/src/index.css`
- All design tokens as CSS custom properties
- `@tailwind` directives (base, components, utilities)

**ESLint Config**: `frontend/.eslintrc.json`
- Enforces token naming convention
- Detects raw hex values
- Detects style violations

**Tailwind Config**: `frontend/tailwind.config.js`
- Maps design tokens to Tailwind utilities
- Extends theme with semantic colors, spacing, etc.

**Token Validation Script**: `frontend/scripts/validate-tokens.js`
- Checks for raw values in code
- Validates token naming patterns
- Generates report for CI

### 4.3 CI/CD Integration

**Workflow**: `.github/workflows/ci.yml`

**Design System Checks** (required on every PR to main):
1. `lint-frontend` - ESLint checks (fails if raw values or naming violations)
2. `validate-design-tokens` - Token validation script (fails if contract violations)
3. `test-frontend` - Runs `npm test` (currently empty, ready for test suite)

**Branch Protection**: Required checks on main (configured in GitHub settings):
- All three design system checks must pass
- Cannot merge if any check fails
- No force-push allowed

---

## 5. CHANGE PROTOCOL & EXTENSION MECHANISM

### 5.1 Proposing New Tokens

**When**: After D0-P4 is locked, but new token needs emerge (e.g., new component types)

**Process**:

1. **Document the need**: Create issue with description
   ```
   Title: "Design System: New token needed - {semantic category}"
   Content:
   - What component/pattern needs this token?
   - Why existing tokens don't work?
   - Proposed token name and value
   - WCAG AA contrast proof (if color)
   ```

2. **Validate naming**: Check against `D0_TOKEN_NAMING_GOVERNANCE.md`
   - Does it fit existing semantic categories? → Fast-track approval
   - Does it require new category? → Requires design + engineering review

3. **Update contract**: If new semantic category, add to governance doc
   ```
   Category: "workflow-state"  # New example
   Pattern: "--state-{name}"
   Example: "--state-processing" (for Centaur LLM workflows)
   ```

4. **Update code**: Add token to:
   - `src/index.css` (CSS custom property)
   - `tailwind.config.js` (Tailwind mapping)
   - `D0_TOKEN_NAMING_GOVERNANCE.md` (for documentation)

5. **Validate**: Run `npm run lint` and `validate-tokens.js`

6. **Merge**: PR requires:
   - ESLint passing ✓
   - Token validation passing ✓
   - Design + engineering sign-off ✓

### 5.2 Extension Governance for New Semantic Categories

**Example**: Skeldir's Centaur workflow requires "processing" state color

**Current D0 Categories**:
- Colors: background, text, status, confidence, data, interactive, border
- Spacing: 12 scale values
- Typography: 11 named text styles
- Effects: shadows, radius, animation timing, easing

**Proposed New Category**: "workflow-state" (for processing/pending/validating)

**Approval Criteria**:
- [ ] Category fills a clear gap in current scheme
- [ ] At least 3 tokens will use this category (not one-off)
- [ ] Naming pattern is unambiguous (no collision with existing categories)
- [ ] Contrast validated (if color category)
- [ ] Documentation updated in governance file

**Ratification**: Add to governance doc, commit to main, CI enforces going forward

---

## 6. EXIT GATE DEFINITIONS

### 6.1 D0-P0 Exit Gate: Contract Coherency Locked

**Met when all are true**:

1. ✓ Max-width semantics resolved
   - **Pass condition**: Architectural decision documented (1440 vs 1280 vs other)
   - **Evidence**: Section 2.2 of this contract (currently deferred to D0-P2)

2. ✓ Token naming convention explicit
   - **Pass condition**: Semantic categories and naming pattern defined
   - **Evidence**: `D0_TOKEN_NAMING_GOVERNANCE.md` created and complete

3. ✓ Integration point explicit
   - **Pass condition**: CSS variables location, Tailwind mapping, import chain documented
   - **Evidence**: Section 2 of this contract (complete)

4. ✓ Validation harness expectations defined
   - **Pass condition**: ESLint config, token validation script, CI gates in place
   - **Evidence**: `.eslintrc.json`, `validate-tokens.js`, CI workflow updated

5. ✓ Engineer sign-off
   - **Pass condition**: Engineer statement exists
   - **Evidence**: "I can scaffold CSS variables and global styles from this contract." (in evidence pack)

**Failure action**: **BLOCK D0-P1**. No token work starts until contract is coherent.

---

### 6.2 D0-P1 Exit Gate: Token Validity and Handoff Readiness

**Met when all are true**:

1. ✓ Token JSONs pass schema validation
   - Test: `validate-tokens.js --schema` passes for all 4 files
   - Files: `skeldir-tokens-{color,spacing,typography,effects}.json`

2. ✓ Semantic categories complete
   - Colors: background, text, status, confidence, data, interactive, border (7 categories)
   - Spacing: 12 scale values
   - Typography: 11 named styles + 2 font families
   - Effects: 5 shadows + 6 radii + 5 durations + 3 easings (19 total)

3. ✓ Engineer sign-off
   - Statement: "I can scaffold CSS variables from these exports."

**Failure action**: **BLOCK D0-P2**.

---

### 6.3 D0-P2 Exit Gate: Token-to-Code Implementation Proof

**Met when all are true**:

1. ✓ CSS variables exist in source
   - Location: `src/index.css` `:root` selector
   - Count: ≥89 variables (47 colors + 12 spacing + 11 typography + 19 effects)

2. ✓ No raw values in Tailwind config
   - `tailwind.config.js` references CSS variables or Tailwind defaults only
   - No hardcoded hex, pixel, or dimension values

3. ✓ Minimal demo UI works
   - Specimen page loads without errors
   - Token values are visible and correct
   - No layout or typography assumptions baked in

4. ✓ Engineer sign-off
   - Statement: "CSS variables are being consumed by components."

**Failure action**: **BLOCK D0-P3**.

---

### 6.4 D0-P3 Exit Gate: Grid Implementability Proven

**Met when all are true**:

1. ✓ All 7 breakpoint artboards designed
   - Mobile (375px, 390px)
   - Tablet (768px, 1024px)
   - Desktop (1280px, 1440px, 1920px)

2. ✓ Grid spec exported to markdown
   - File: `docs/design/tokens/skeldir-grid-spec.md`
   - Content: Columns, gutters, margins for each breakpoint

3. ✓ Engineer sign-off
   - Statement: "I can implement responsive grid from this spec."

**Failure action**: **BLOCK D0-P4**.

---

### 6.5 D0-P4 Exit Gate: Typography Enforceability and Mapping

**Met when all are true**:

1. ✓ 11 text styles created and published
   - Display/Large, Display/Medium
   - Heading/Large, Heading/Medium, Heading/Small
   - Body/Large, Body/Medium, Body/Small
   - Label/Large, Label/Medium
   - Mono/Default

2. ✓ Zero orphan text in design files
   - All sample text uses defined styles (verified by Figma search)

3. ✓ Engineer sign-off
   - Statement: "Text styles map to CSS typography scale."

**Failure action**: **BLOCK D0-P5**.

---

### 6.6 D0-P5 Exit Gate: WCAG-Valid Color System + Engineering Mapping

**Met when all are true**:

1. ✓ 47 color styles created and published

2. ✓ All text/background pairs pass WCAG AA
   - Body text pairs: 4.5:1 minimum
   - Large text pairs (18pt+ or 14pt bold): 3:1 minimum
   - Interactive elements: 3:1 minimum
   - Documentation: `docs/design/tokens/skeldir-color-contrast-matrix.md`

3. ✓ Contrast matrix exists and is auditable
   - Format: Table with color pair, contrast ratio, pass/fail
   - Coverage: All foreground/background combinations

4. ✓ Engineer sign-off
   - Statement: "Color styles map to CSS variables."

**Failure action**: **BLOCK D0 MACRO completion**.

---

### 6.7 D0 MACRO Exit Gate: Foundation Ready for D1

**Met when all are true**:

1. ✓ D0-P0 through D0-P5 all passed
2. ✓ All token JSONs valid and exported
3. ✓ All token JSONs referenced by CI validation
4. ✓ CSS variables exist and are validated in CI
5. ✓ Engineering can scaffold components without interpretation

**Failure action**: **BLOCK D1 (Atomic Components)**. No component work starts until foundation is locked.

---

## 7. PRECEDENCE ORDER: RESOLVING CONFLICTS

### 7.1 Constraint Hierarchy

When multiple documents or constraints seem to conflict, resolve using this precedence:

1. **WCAG AA Accessibility** (regulatory, non-negotiable)
2. **This D0 Contract** (architectural decision, locked by exit gates)
3. **SCAFFOLD.md** (implementation reality, descriptive not prescriptive)
4. **Design Plans** (aspirational, may be revised during lock phases)
5. **Engineering Preferences** (nice-to-have, overrideable)

### 7.2 Example: Max-Width Decision

**Situation**: Design plan mentions both 1440px and 1280px max-widths. Which is authoritative?

**Resolution**:
- **Current status**: Decision deferred to D0-P2 (Grid System)
- **Handling**: Add explicit rule to this contract before D0-P2 begins:
  - Option A: "1440px container max-width, 1280px content region max-width"
  - Option B: "Single 1280px max-width for entire layout"
  - Option C: "Responsive: 100% on mobile, 1280px on desktop, 1440px on ultra-wide"
- **Amendment process**: Update this contract, add evidence to `docs/forensics/D0_P0_EVIDENCE.md`, get sign-off from leads

### 7.3 Known Ambiguities Requiring Resolution

**Current**: None. All major constraints are defined in Sections 2-3.

**If new ambiguities arise**: File issue to `docs/design/` with tag `contract-ambiguity`, include:
- What constraint is ambiguous?
- Which documents conflict?
- Proposed resolution
- Impact assessment

---

## 8. GOVERNANCE ROLES & RESPONSIBILITIES

### 8.1 Contract Steward

**Role**: Maintains coherence of this contract and all referenced documents

**Responsibilities**:
- Reviews all `design-system-contract-change` issues
- Ensures changes don't create downstream conflicts
- Updates evidence pack when precedence changes
- Communicates to design and engineering leads

**Currently**: TBD (assign via CODEOWNERS)

### 8.2 Design System Architect

**Role**: Leads design phase work (D0-P0 through D7)

**Responsibilities**:
- Executes design phases according to this contract
- Ensures deliverables meet exit gates
- Proposes new tokens via extension process
- Provides engineer sign-offs at each gate

**Currently**: TBD (assign via CODEOWNERS)

### 8.3 Frontend Engineer Lead

**Role**: Ensures engineering can execute contracts

**Responsibilities**:
- Reviews contracts for implementability
- Maintains ESLint and validation tooling
- Provides sign-offs at engineering gates
- Escalates conflicts early

**Currently**: TBD (assign via CODEOWNERS)

---

## 9. DOCUMENT REFERENCES & RELATED ARTIFACTS

### 9.1 Referenced Documents

- `docs/design/D0_TOKEN_NAMING_GOVERNANCE.md` - Naming rules (required read)
- `docs/forensics/D0_P0_EVIDENCE.md` - Investigation findings (evidence record)
- `frontend/SCAFFOLD.md` - Current scaffold description (reference only)
- `frontend/.eslintrc.json` - ESLint validation configuration (enforcement)
- `frontend/scripts/validate-tokens.js` - Token validation script (enforcement)
- `.github/workflows/ci.yml` - CI gate configuration (enforcement)

### 9.2 Design Plan Documents (Aspirational, Subordinate to This Contract)

- `Skeldir_Frontend_Design_Systems_Implementation_Plan.md` - Full D0-D7 design plan
- `D0 linearly hierarchical implementa.md` - Simplified D0 plan

**Note**: Design plans inform this contract but do not override it once locked.

---

## 10. VERSION HISTORY

| Version | Date | Change | Status |
|---------|------|--------|--------|
| 1.0 | Feb 2, 2026 | Initial contract lock | ACTIVE |

---

## 11. EFFECTIVE DATE & ENFORCEMENT

**Effective Date**: Upon merge to main with CI green

**Enforcement Mechanisms**:
1. ESLint configuration (rejects hardcoded values)
2. Token validation script (rejects naming violations)
3. Branch protection rules (requires all CI checks pass)
4. Code review (design + engineering sign-off required)

**No exceptions without explicit amendment to this contract.**

---

## CONCLUSION

This contract locks the D0 phase foundation and provides clear, measurable criteria for downstream phases. Every constraint is grounded in the actual codebase environment and enforced by CI automation.

**This is not a proposal. This is a lock. Proceed to D0-P0 remediation and merge.**

---

*Skeldir Design System D0 Phase Contract v1.0*
*Locked February 2, 2026 | Governs D0-P0 through D0-P5 and all downstream phases*
