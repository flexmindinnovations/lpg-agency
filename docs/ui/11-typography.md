# 11 — Typography

## Purpose
Defines the typography scale, heading system, body/caption/label text, table typography, receipt/printing fonts, and responsive typography behavior.

## 1. Type Scale (Token-Driven)

| Token | Size | Weight | Line Height | Use |
|---|---|---|---|---|
| display | 32px | 700 | 1.2 | Rare, large KPI numbers only |
| heading1 | 24px | 700 | 1.2 | Page titles |
| heading2 | 18px | 600 | 1.3 | Section headers, drawer titles |
| heading3 | 16px | 600 | 1.3 | Card titles, sub-sections |
| body | 16px | 400 | 1.5 | Default body text |
| bodySmall | 14px | 400 | 1.5 | Secondary/dense UI text, Data Grid cells |
| caption | 12px | 400 | 1.4 | Timestamps, helper text |
| label | 14px | 500 | 1.4 | Form labels, badges |

All values are typography component tokens (`09-design-tokens.md` section 5) — no screen ever specifies a raw font-size.

## 2. Heading System
Strict hierarchy: heading1 appears once per screen (the page title), heading2 for major sections, heading3 for cards/sub-sections — never skipping a level (accessibility requirement: heading levels must nest correctly for screen reader navigation, `17-accessibility.md`).

## 3. Body Text
Default body (16px) for all primary reading content; bodySmall (14px) reserved for dense, scannable contexts (Data Grid cells, compact list items) where the user is scanning rather than reading — never used for primary content a user must carefully read.

## 4. Captions and Labels
- Caption: metadata that supports but isn't the primary content — timestamps, "last updated by," helper text under a form field.
- Label: form field labels and Badge text — slightly heavier weight (500) than body text to read as structural, not conversational.

## 5. Table Typography
Data Grid cells use bodySmall for data values, label-weight for column headers (with aria-sort semantics, `14-data-grid-guidelines.md`) — numeric columns are right-aligned with tabular figures (fixed-width digits) so columns of numbers align visually, critical for the Accountant persona scanning financial columns.

## 6. Receipts and Printing Fonts
- Print output (`18-printing-ux.md`) uses a monospace-influenced typeface for thermal receipts (58/80mm) since thermal printers render fixed-width fonts most reliably and legibly at small sizes — a deliberate, printing-specific typography decision distinct from the screen type scale.
- A4/PDF documents (invoices, GST reports) use the same typeface family as the screen UI for brand consistency, at print-appropriate sizes (10-11pt body, per `docs/data/16-printing-data-model.md`).

## 7. Responsive Typography
- Type scale does not fluidly resize with viewport (avoids unpredictable line-wrapping in the Dashboard's dense layouts) — instead, a small number of discrete adjustments apply at breakpoints: heading1 steps down from 24px to 20px below the tablet breakpoint, all other sizes remain constant.
- Customer App (consumer context) uses a slightly larger base body size (17px vs 16px) than the Dashboard, reflecting the broader age/accessibility range of the Customer persona (`02-user-personas.md`) — a deliberate, documented exception to the shared type scale, still fully token-driven.

## Best Practices
- Line length for body text is capped (via container max-width) at approximately 75 characters for readability in long-form content — Data Grid cells are exempt given their inherently constrained width.
- Font weight is never used as the sole way to convey emphasis in body text at small sizes — color/icon emphasis is preferred at small sizes.

## Risks
- System font stacks render slightly differently across OS/browser — mitigated by testing the type scale's line-height/spacing tolerances across the platform's target browser/OS matrix rather than assuming pixel-perfect consistency.

## Alternatives Considered
- Fluid/clamp-based responsive typography — rejected in favor of discrete breakpoint steps, prioritizing predictable layout over smooth scaling, given the Dashboard's data-density requirements.

## Future Scalability
- If a custom webfont is adopted later, the token-driven type scale absorbs that change as a single font-family token swap, with no changes needed to the size/weight/line-height scale itself.
