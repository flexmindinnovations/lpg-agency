# 12 — Component Library

## Purpose
Catalogs every reusable component in the shared design system, organized by category, as the index that `13-component-specifications.md` details individually.

## 1. Form Controls
Button (primary/secondary/tertiary/destructive/icon), Input (text/number/password), Select, Multi-Select, Autocomplete, Search Field, Textarea, Checkbox, Radio Group, Toggle/Switch, Numeric Stepper, Date Picker, Date Range Picker, File Upload.

## 2. Navigation
Sidebar Nav Item, Top Bar, Breadcrumb, Tabs, Command Palette, Pagination, Stepper (wizard progress indicator).

## 3. Feedback and Overlays
Dialog (modal), Drawer, Bottom Sheet (mobile), Toast, Snackbar, Banner (inline page-level alert), Tooltip, Popover, Loading Skeleton, Progress Bar, Spinner.

## 4. Data Display
Data Grid (AG Grid Enterprise-based on Dashboard), Card, Badge, Status Pill, Avatar, Timeline/Activity Feed, Key-Value Summary Panel, Empty State, Chart (line/bar/donut), Calendar (month/week/day view for route/report date navigation).

## 5. Domain-Specific Components
Receipt Viewer, Print Preview, Barcode Viewer, QR Viewer, Signature Pad, Map (delivery address/route visualization), Cylinder Balance Card (a specialized Card variant showing filled/empty/damaged counts per cylinder type), Order Status Stepper (renders the Order state machine visually), SLA Countdown Badge (complaint-specific).

## 6. Layout Primitives
Page Header, Section, Grid (12-column layout helper), Divider, Spacer.

## Component-to-Screen Mapping (Representative)

| Component | Used In |
|---|---|
| Data Grid | Order Queue, Customer List, Invoice List, Complaint Queue, Stock Overview |
| Order Status Stepper | Order Detail (Dashboard), Order Tracking (Customer App) |
| Signature Pad | Delivery Confirmation (Driver App) |
| Barcode Viewer, QR Viewer | Invoice Detail and Print Preview, Thermal Receipt |
| Cylinder Balance Card | Customer Detail plus Ledger, Customer App Home |
| SLA Countdown Badge | Complaint Queue, Complaint Detail |
| Map | Route Planning Board, Stop Navigation (Driver App) |
| Wizard Stepper | Tenant Onboarding flow (if surfaced in-product), multi-step forms |

## Platform Implementation Notes
- Angular: every component in this catalog is a standalone component in the shared UI library, built on Angular Material plus Angular CDK primitives where a suitable base exists (Dialog, Drawer via CDK Overlay, Autocomplete), with AG Grid Enterprise specifically for Data Grid (`14-data-grid-guidelines.md`).
- Flutter: an equivalent widget exists in the shared design system package for every component used in the Customer/Driver apps (a strict subset of this catalog — Data Grid, Command Palette, and several Dashboard-only components have no Flutter equivalent since they do not apply to a mobile context).

## Best Practices
- No screen introduces a bespoke, one-off UI pattern without first checking this catalog — a new pattern is only justified if genuinely reusable and gets added here, not built inline.
- Domain-specific components (section 5) are still built from the same primitive/semantic tokens as generic components — a Cylinder Balance Card uses the same Card component-token base as any other card, extended with domain-specific content, not restyled from scratch.

## Risks
- Component catalog growth without governance leads to near-duplicate components (e.g., two slightly different status badge patterns) — mitigated by the design-system-owner review gate referenced in `08-design-system.md`.

## Alternatives Considered
- Building Data Grid features from scratch rather than AG Grid Enterprise — rejected; AG Grid Enterprise's built-in sorting, filtering, grouping, column-pinning, virtual-scroll, and export capabilities directly satisfy `14-data-grid-guidelines.md`'s requirements without reinventing well-solved enterprise-grid problems.

## Future Scalability
- The Angular/Flutter component parity table is the reference used when a new Phase 2 screen is designed — if its needed components already exist in both catalogs, implementation is largely composition, not new component design.
