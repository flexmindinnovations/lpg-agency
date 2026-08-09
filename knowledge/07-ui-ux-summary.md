# UI/UX Summary

## Purpose

This document provides a high-level summary of the User Experience (UX), Design System, Accessibility, and UI principles used throughout the LPG Agency Management Platform.

It serves as the primary UI reference for developers and AI coding agents before reading the detailed design documentation.

For detailed specifications refer to:

- docs/ui/
- docs/ui/08-design-system.md
- docs/ui/ (journeys, personas, screens)

---

# Design Vision

The application should provide a modern enterprise SaaS experience.

Users should feel that the application is:

- Fast
- Simple
- Professional
- Consistent
- Accessible
- Reliable

The interface should minimize cognitive load while maximizing operational efficiency.

---

# Design Philosophy

The design language is inspired by modern enterprise platforms such as:

- Linear
- GitHub
- Vercel
- Stripe Dashboard
- Atlassian
- Microsoft Fluent
- Notion

The application should avoid:

- Cluttered layouts
- Heavy gradients
- Outdated enterprise styling
- Excessive animations
- Inconsistent spacing
- Hardcoded UI values

---

# Design Principles

Every screen should prioritize:

- Simplicity
- Consistency
- Discoverability
- Accessibility
- Productivity
- Performance
- Responsiveness

Every interaction should reduce the number of clicks required to complete business operations.

---

# User Experience Goals

The primary UX goals are:

- Minimize learning curve
- Support keyboard-first workflows
- Reduce repetitive actions
- Enable rapid data entry
- Improve operational visibility
- Support high-volume daily operations

---

# Design Token Philosophy

The application is fully Design Token driven.

Never hardcode:

- Colors
- Typography
- Spacing
- Border Radius
- Shadows
- Elevation
- Motion
- Icons
- Component Sizes

All UI values originate from centralized Design Tokens.

---

# Theme System

Supported themes:

- Light Theme
- Dark Theme
- High Contrast Theme

Future support:

- Tenant Branding
- Custom Primary Colors
- Custom Logos

Theme switching should be immediate and consistent across all applications.

---

# Color System

Colors are semantic.

Examples:

- Primary
- Secondary
- Success
- Warning
- Danger
- Info
- Surface
- Background
- Border
- Text
- Muted
- Disabled
- Interactive

UI components should reference semantic tokens only.

---

# Typography

Typography uses a predefined scale.

Examples:

- Display
- Heading
- Title
- Subtitle
- Body
- Caption
- Label
- Table Text
- Receipt Text

Arbitrary font sizes are not permitted.

---

# Layout Principles

Layouts should follow:

- Responsive Grid
- Consistent Spacing
- Maximum Readability
- Logical Information Hierarchy
- Progressive Disclosure

Every screen should emphasize the primary task.

---

# Navigation

Primary navigation includes:

- Sidebar
- Top Navigation
- Breadcrumbs
- Global Search
- Command Palette
- Favorites
- Recent Items

Navigation should remain consistent throughout the application.

---

# Dashboard Experience

The dashboard provides:

- KPI Cards
- Operational Metrics
- Alerts
- Pending Actions
- Recent Activity
- Quick Actions
- Reports
- Notifications

Dashboards should be customizable in future releases.

---

# Forms

Enterprise forms should support:

- Validation
- Auto Save
- Draft Mode
- Undo
- Redo
- Dynamic Fields
- Error Summaries
- Keyboard Navigation

Forms should minimize user effort.

---

# Data Tables

Enterprise tables should support:

- Sorting
- Filtering
- Searching
- Pagination
- Infinite Scroll
- Column Chooser
- Column Resize
- Sticky Headers
- Bulk Actions
- Export
- Saved Views

Large datasets should use virtualization.

**Implementation: AG Grid, behind an application-level wrapper** in `libs/shared/ui` (ADR-020, amended by ADR-028). **AG Grid Community is the default; AG Grid Enterprise is optional**, enabled per grid only where a documented feature requirement needs an Enterprise-only capability (e.g. row grouping). Feature libraries configure the wrapper through an application-defined contract and must never import AG Grid types or call its APIs directly. Accessibility is verified once, in the wrapper, per ADR-011. Where Enterprise is used, it requires a **commercial licence**, supplied as build-time configuration and never committed — the same rule applies to the PrimeNG licence key.

---

# Component Strategy

The UI is built using reusable components.

Examples:

- Buttons
- Inputs
- Selects
- Autocomplete
- Cards
- Dialogs
- Drawers
- Tables
- Forms
- Tabs
- Badges
- Charts
- Toasts
- Notifications
- Receipt Viewer
- Print Preview

New components should only be introduced when reuse is not possible.

---

# Accessibility

The platform complies with WCAG 2.2 AA.

Accessibility includes:

- Keyboard Navigation
- Screen Reader Support
- Focus Management
- ARIA Labels
- Color Contrast
- Reduced Motion
- Semantic HTML
- Accessible Tables
- Accessible Forms
- Accessible Dialogs

Accessibility is mandatory.

---

# Keyboard Productivity

Enterprise keyboard shortcuts include:

- Ctrl + K → Global Search
- Ctrl + Shift + P → Command Palette
- Ctrl + N → Create New
- Ctrl + S → Save
- Ctrl + P → Print
- Esc → Close Dialog
- Arrow Keys → Table Navigation
- Enter → Open Record
- Delete → Delete Record (permission controlled)

Keyboard support should be available across the application.

---

# Printing Experience

Printing is a first-class feature.

Supported outputs:

- Delivery Receipt
- Invoice
- Payment Receipt
- Cash Receipt
- Customer Ledger
- Inventory Reports
- Driver Reports
- GST Reports

Supported formats:

- Thermal Printer
- A4
- PDF
- Barcode
- QR Code

Every printable document should have a preview.

---

# Responsive Strategy

Supported devices:

- Desktop
- Laptop
- Tablet
- Mobile

The Agency Dashboard is desktop-first.

Customer and Driver applications are mobile-first.

---

# Motion & Feedback

Animations should be subtle.

Examples:

- Loading Indicators
- Success Feedback
- Error Feedback
- Page Transitions
- Toast Notifications
- Skeleton Screens

Animations should never reduce usability.

Respect `prefers-reduced-motion`.

---

# Empty, Loading & Error States

Every screen should define:

- Loading State
- Empty State
- Error State
- Permission Denied
- Offline State
- Success State

No screen should appear unfinished during data loading.

Errors arrive from the API as RFC 7807 Problem Details (ADR-021); a single HTTP interceptor translates them into a typed application error surfaced through the shared notification component. Screens do not parse error payloads individually.

---

# Live Updates

The Dashboard receives real-time updates over WebSocket (`docs/architecture/16-realtime-architecture.md`) for order status, delivery status, driver assignment, dispatcher operations, and dashboard KPIs.

The connection is owned by **one service** in `libs/shared/data-access`, never opened per feature. Connection state is surfaced in the UI rather than silently showing stale data.

**A view that only renders correctly while a socket is open is a defect** — real-time is an enhancement layered on top of REST-fetched state, never the source of truth.

---

# AI Design Guidelines

When creating or modifying UI:

1. Reuse existing components.
2. Follow the Design Token system.
3. Preserve accessibility.
4. Maintain consistent spacing and typography.
5. Support keyboard navigation.
6. Design for responsive layouts.
7. Consider printing requirements.
8. Keep interactions simple and predictable.

Never introduce hardcoded styles or inconsistent interaction patterns.

---

# Related Documentation

Refer to:

- docs/ui/
- docs/ui/08-design-system.md
- docs/engineering/
- docs/architecture/