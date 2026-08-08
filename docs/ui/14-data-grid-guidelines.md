# 14 — Data Grid Guidelines

## Purpose
Designs the enterprise Data Grid pattern used throughout the Dashboard (AG Grid Enterprise-based): sorting, filtering, grouping, column chooser, column pinning, virtual scroll, pagination, saved views, bulk actions, keyboard navigation, accessibility.

## 1. Sorting
- Click a column header to sort ascending, click again for descending, click again to clear. Shift+click adds a secondary sort column.
- Sort state persists in the URL query string (shareable, back-button-safe) and in Saved Views (section 8).
- Server-side sorting for all grids (never client-side sort of a full unpaginated dataset), matching `docs/data/10-api-design-guidelines.md` section 6 sort parameter convention.

## 2. Filtering
- Column-level filters (text contains, numeric range, date range, enum multi-select) available via a filter icon in each column header.
- A persistent top-of-grid Filter Bar surfaces the most common filters for that module (e.g. Order Queue's Filter Bar always shows Status and Date Range without needing to open per-column filter menus) — reduces clicks for the highest-frequency filter operations.
- Filters combine with AND logic across columns; within a single enum filter, OR logic (e.g. Status equals Confirmed OR Assigned).
- Server-side filtering via the whitelisted filter-expression subset (`docs/data/10-api-design-guidelines.md` section 5).

## 3. Grouping
- Available on select grids where it adds real value (e.g. grouping the Cylinder Movement report by Cylinder Type, or Orders by Branch for multi-branch tenants) — not enabled universally, since grouping adds complexity that most list screens (Customer List, Complaint Queue) don't need.
- Grouped rows show an aggregate summary (count, sum) in the group header row.

## 4. Column Chooser
- A Columns button opens a panel listing all available columns with checkboxes to show/hide, and drag-to-reorder.
- Certain columns are pinned-mandatory (e.g. the primary identifier column is always visible) and excluded from the hide option.
- Column visibility/order preference is saved per user, per grid (not global).

## 5. Column Pinning
- Users can pin columns left (e.g. the identifier/name column) or right (e.g. a row-actions column) so they remain visible during horizontal scroll on wide grids.
- The row-actions column (row-level menu: view, edit, cancel, etc.) is pinned-right by default on every grid.

## 6. Virtual Scroll
- All grids use virtual row rendering (AG Grid's built-in row virtualization) — only visible rows are rendered in the DOM, regardless of total dataset size, keeping scroll performance smooth even for the Ledger Transaction history's potentially thousands of rows per customer.
- Combined with server-side pagination (section 7) rather than loading the full dataset into virtual scroll — virtual scroll handles the current page's smoothness, pagination bounds the total data transferred.

## 7. Pagination
- Offset-based pagination (page number plus page size selector, default 25 per page, options for 50/100) for standard list grids, matching `docs/data/10-api-design-guidelines.md` section 4.
- Cursor-based load-more pattern (not numbered pages) for append-only history grids (Ledger Transactions, Inventory Transactions, Audit Log) where deep page-number jumping isn't a meaningful user need.

## 8. Saved Views
- A user can save the current combination of filters, sort, column visibility/order, and grouping as a named View (e.g. "My Overdue Complaints").
- Saved Views appear in a dropdown at the top of the grid and can be pinned to the Sidebar's Favorites section (`04-information-architecture.md` section 7).
- Views are personal by default; a future (Phase 2) share-view-with-team capability is a documented extension point, not built at Phase 1.

## 9. Keyboard Navigation

| Key | Action |
|---|---|
| Arrow keys | Move focus one cell/row |
| Home / End | Jump to first/last column in the row |
| Ctrl+Home / Ctrl+End | Jump to first/last cell in the grid |
| Page Up / Page Down | Scroll by one visible page |
| Enter | Open the focused row's detail view |
| Space | Toggle row selection (when selection mode is active) |
| Ctrl+A | Select all rows on the current page |
| Forward slash | Focus the grid's filter search field |
| Escape | Clear focus from a filter input, return focus to the grid |

## 10. Bulk Actions
- Selecting one or more rows (checkbox column, leftmost) surfaces a contextual Bulk Action Bar above the grid, replacing the page header's primary action temporarily.
- Bulk actions always confirm before executing if destructive (e.g. "Cancel 12 orders?") and always report per-item results afterward (matching the API's per-item bulk-operation response shape) — a bulk action never silently fails on a subset without telling the user which items failed and why.

## 11. Responsive Behavior — Mobile Card-List Conversion
Below the tablet breakpoint, every Data Grid converts to a stacked card list: each row becomes a card showing the 2-3 most important fields (configured per grid) plus a view-details affordance — full table scrolling is not offered on mobile, since horizontal scrolling of a dense table is a poor mobile experience. Sorting/filtering remain available via a collapsed filter drawer.

## 12. Accessibility
- Grid role with proper row, gridcell, and columnheader semantics.
- Sort-state attribute on sortable headers, updated live.
- Bulk-selection count changes announced via a polite live region (e.g. "3 rows selected").
- Virtual scrolling implementation ensures screen readers can still navigate the full logical row set (via a row-count attribute reflecting total, not just rendered, rows) — a common accessibility pitfall with virtualized grids that this platform explicitly guards against.

## Best Practices
- Every grid in the platform is built from the same shared Data Grid component (`12-component-library.md`), configured per module — never a bespoke table implementation for a specific screen.
- Default page size, default sort, and default filter (if any) are chosen per module to match the most common real-world task (e.g. Order Queue defaults to sorting by Requested Date ascending, status filter defaulted to active/pending statuses, not showing Closed/Cancelled by default).

## Risks
- AG Grid Enterprise licensing/bundle-size cost — accepted given the enterprise feature requirements (grouping, column pinning, advanced filtering) genuinely needed here; a lighter-weight grid library was considered and rejected (see Alternatives).

## Alternatives Considered
- A lightweight/custom-built table component — rejected; the feature set required (server-side everything, grouping, column pinning, saved views, virtual scroll, accessibility) is exactly AG Grid Enterprise's core value proposition, and building/maintaining equivalent functionality in-house is a worse 10-year investment than licensing a purpose-built product.

## Future Scalability
- Saved Views' share-with-team extension point and potential future export-scheduling integration (tying into the Reporting module's async export jobs) are both additive to the current grid architecture, requiring no restructuring.
