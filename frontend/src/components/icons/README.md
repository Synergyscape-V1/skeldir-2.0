# Icon Usage Guide — Skeldir Design System

> D3.7 §6.4 deliverable. This document standardizes icon usage across the
> Skeldir frontend to prevent silent drift and accessibility regressions.

## Import Convention

Always use **named imports** from `lucide-react`. Do NOT use barrel imports
or re-export icons through a local wrapper:

```tsx
// CORRECT
import { ChevronRight, AlertCircle } from 'lucide-react'

// WRONG — barrel re-export adds bundle weight and indirection
import { ChevronRight } from '@/components/icons'
```

## Sizing

Use three standard sizes tied to the D0 spacing scale:

| Size Token | Pixels | Tailwind Class | Usage |
|------------|--------|----------------|-------|
| `sm`       | 16px   | `h-4 w-4`     | Inline with text, badges, buttons |
| `md`       | 20px   | `h-5 w-5`     | Standalone icons, navigation items |
| `lg`       | 24px   | `h-6 w-6`     | Page headers, empty states, alerts |

```tsx
<AlertCircle className="h-4 w-4" />   // sm — inline
<AlertCircle className="h-5 w-5" />   // md — standalone
<AlertCircle className="h-6 w-6" />   // lg — header
```

Do NOT use arbitrary pixel values (`w-[18px]`). Stick to the scale above.

## Color Inheritance

Lucide icons use `currentColor` by default. Let parent text color cascade:

```tsx
// CORRECT — inherits parent color
<span className="text-destructive">
  <AlertCircle className="h-4 w-4" />
  Error occurred
</span>

// WRONG — hardcoded color breaks dark mode
<AlertCircle className="h-4 w-4 text-red-500" />
```

Exception: when an icon deliberately needs a fixed semantic color (e.g.,
success green checkmark), use the D0 token-mapped Tailwind class:

```tsx
<CheckCircle2 className="h-4 w-4 text-verified" />
```

## Accessibility Labeling

### Decorative icons (paired with visible text)

When the icon is purely decorative and adjacent text conveys the meaning,
hide it from assistive technology:

```tsx
<Button>
  <AlertCircle className="h-4 w-4" aria-hidden="true" />
  Report Issue
</Button>
```

### Meaningful icons (no adjacent text)

When the icon is the sole conveyor of meaning (e.g., an icon-only button),
provide an accessible label:

```tsx
<Button variant="ghost" size="icon" aria-label="Close dialog">
  <X className="h-4 w-4" />
</Button>
```

### Icon + tooltip pattern

For icon-only buttons with tooltips, the `aria-label` on the button takes
precedence. The tooltip is supplementary:

```tsx
<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="ghost" size="icon" aria-label="Download report">
      <Download className="h-4 w-4" />
    </Button>
  </TooltipTrigger>
  <TooltipContent>Download report</TooltipContent>
</Tooltip>
```

## Decision Tree

```
Is the icon next to visible text that explains it?
  YES → aria-hidden="true" on the icon
  NO  → Does the parent interactive element have aria-label?
    YES → aria-hidden="true" on the icon (label is on parent)
    NO  → Add aria-label to the parent element
```

## Common Mistakes

1. **Forgetting `aria-hidden`** on decorative icons — screen readers will
   announce the SVG path data or nothing useful.
2. **Using `title` prop** instead of `aria-label` — `title` creates a
   tooltip on hover but is not reliably announced by screen readers.
3. **Inconsistent sizing** — mixing `h-4 w-4` and `h-[18px] w-[18px]`
   creates visual jitter in alignment.
4. **Hardcoded colors** — breaks dark mode. Always use `currentColor`
   inheritance or D0 token classes.

---

*Cursor workflow: Created per D3.7 §6.4. To validate, run Storybook a11y
panel and check that icon-containing components have 0 critical violations.*
