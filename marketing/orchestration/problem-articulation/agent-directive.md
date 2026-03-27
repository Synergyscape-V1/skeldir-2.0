# Problem Articulation Multi-Agent Directive

## Locked Directive Text

Implement a replacement for `marketing/src/components/layout/ProblemStatement.tsx` that matches the provided reference image exactly.

Ground truth:
- Reference image only.
- Do not reinterpret as cards-only layout.

Must include, in this order:
1. Main heading: "Why Your Current Attribution Is Lying to You"
2. Supporting subheadline copy from reference
3. "Budget vs. Actual Revenue Contribution" chart block with platform rows and percentages
4. Overfunded/underfunded annotations and directional callouts
5. Boxed $500K/year misallocation callout with source text
6. Bottom bullet list with spend tiers and source text

Hard constraints:
- Replace only `ProblemStatement` section.
- Do NOT modify `SolutionOverview` or sections below it.
- Keep homepage section order unchanged.
- Do not invent numbers/copy not present in reference.
- Do not simplify into alternate architecture (tabs, carousel, 3-card-only summary).

Deliverables:
- Code changes
- Desktop screenshot (1726x928)
- Mobile screenshot (390x844)
- Self-checklist proving each required element exists
- Build/lint status
