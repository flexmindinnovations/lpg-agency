# 71 — Simpler screens: invoice drawer, glass cards, linked phones, cylinders and prices

**Requested 2026-11-27** with five screenshots. The owner's rule for this and
later work: the platform must be usable without training; simplify wherever we
can, following industry practice.

## Items

1. Invoice drawer: actions stay at the bottom, like other drawers.
2. Cards: lower background opacity (glass look). No `backdrop-filter` — it made
   scrolling slow before.
3. Invoice PDF: the file name carries the invoice number and the time.
4. Label and value rows: one format everywhere (the order page's: a label
   column with values beside it), including the order quick view.
5. Row action buttons centred in their rows.
6. Tables must not run past their width when columns can be dropped.
7. Online payments: space under the Razorpay key fields.
8. Linked Devices: a phone that signs in must appear in the list.
9. Cylinder types and Pricing: one screen; set the price while adding.

## Decisions

- **Item 3.** A PDF opened in a browser tab is saved under a random name, so
  the drawer gets **Download PDF**, which saves
  `<invoice number>_<date>_<time>.pdf`. **Print PDF** stays. The PDF's own title
  carries the same name.
- **Item 5.** Measured on the running app: already centred (0.2 px) after
  feature 70's fix; the screenshot shows the earlier build.
- **Item 6.** Fixed in the shared grid: `priority: 'low'` columns are dropped
  when the columns no longer fit, not only below a fixed width.
- **Item 8.** Cause: the agency's phone setting defaulted to **Off**, which
  records nothing. Phones are now always recorded. The three-way setting is one
  switch, **Approve new phones first**. Recording never stops a sign-in. A phone
  the admin **blocks** is refused whether or not the switch is on (ADR-071
  amendment).
- **Item 9.** One screen, **Cylinders & Prices**. Adding a cylinder asks for its
  price; the GST rate is filled in from the type (5% domestic, 18% commercial)
  and can be changed. HSN sits under **More options**. The old Pricing address
  redirects here. A price on its own no longer stops a cylinder being deleted,
  because every new cylinder has one; it still fixes the size (ADR-079
  amendment).
- **Labels and values** (item 4) and **one pinned footer per drawer** (item 1)
  are now rules in `AGENTS.md`. The first is also checked by
  `ui-conventions.spec.ts`; the second is not. Totals strips above a table are
  not records and stay as they are. The Customer profile drawer keeps its
  buttons in one row at the top, as the owner asked earlier.
- **Audit log.** Every recorded action has a name in plain words. The Action
  filter offered sign-in and phone actions that the API refused; it now accepts
  them.

## Follow-up after the first review

- **Two drawer widths.** The side drawers used about eight different widths.
  Each is now `--drawer-width` (36rem) or `--drawer-width-wide` (48rem, for the
  audit entry and the trip board); a phone is full width. The customer profile
  and the notification panel keep their own size. The rule is in `AGENTS.md`
  and `ui-conventions.spec.ts`.
- **Labels.** The shared label column is wider, so "Domestic · Mitha Nagar"
  fits on one line on a desktop.
- **Audit entry.** Field names keep their words whole, "Before" shows only when
  there is an earlier value, and two fields read "IP address" and
  "Browser or app".
- **Preview dialogs** (such as Branch Details) have no line under the last
  block.
- **Tables** use the card background. Inside a section card they add none; the
  header stays solid.
- **Cylinder drawer** against a server without `delete_blocked_by`: it falls
  back to `used_in`, so Edit works and the reason is shown. The advice no longer
  asks to deactivate a record that is already inactive.

## Second follow-up

- **Card heading line.** "Add document" and the reports' "Export CSV" sit beside
  the card's heading. A component inside a card does this with
  `<ng-template lpgCardActions>`.
- **Export button** is a secondary button with the words "Export CSV", in place
  of the blue icon-only square.
- **Tables in cards** run edge to edge without side borders. With nothing under
  one, it also ends at the card's bottom edge. Notification rows do the same.
- **No line after the last row** of a table that ends a section.
- **Compliance documents** are plain rows divided by lines, no longer boxes
  inside a card.
- **GST check.** A cylinder whose rate is not the usual one (5% domestic, 18%
  commercial) shows a warning on the page, in its drawer and beside the rate
  field. It never blocks saving: the accountant decides.

## Not done: ideas for a later round

From a domain review (a model's advice, not an owner decision).

Safe to do: replace the Configuration page's keys and values with a grouped
form; a shorter menu (Branches, Godowns and Audit Log under Settings; one
Payments page; "Features" instead of "Feature Flags"); an order header with one
next-step button and **More**; optional delivery proof folded away; customer
onboarding in 2 steps instead of 5; one **More** menu on Inventory; fewer
buttons on the invoice footer (one **Print** menu).

Needs the owner: hiding the AI, WhatsApp and OMC settings; confirming and
closing orders automatically; keeping only one delivery code (OTP or DAC);
which of date of birth and KYC are required; one **Add driver** form; optional
vehicle make and model (server rules not checked); merging Users and Employees.
