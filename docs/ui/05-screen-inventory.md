# 05 — Screen Inventory

## Purpose
Master inventory of every screen across all three apps, categorized by module, with purpose, roles, primary actions, dependencies, expected data, and estimated complexity (S/M/L/XL, roughly correlating to implementation effort).

## Legend
Complexity: **S** = single form/simple view, **M** = list/detail with moderate logic, **L** = Data Grid or multi-step flow, **XL** = complex interactive screen (e.g., route planning board).

## Agency Web Dashboard

| # | Screen | Module | Purpose | Roles | Primary Actions | Dependencies | Expected Data | Complexity |
|---|---|---|---|---|---|---|---|---|
| D-01 | Login | Auth | Staff authentication | All staff | Sign in | Identity API | credentials | S |
| D-02 | Home / KPI Overview | Home | At-a-glance operational health | All staff | Navigate to detail | Reports API | KPI aggregates | M |
| D-03 | Order Queue | Orders | List/filter orders | Manager, Dispatcher, AgencyAdmin | Create, filter, bulk-cancel, add-to-route | Orders API | Order list | L |
| D-04 | Order Detail | Orders | Full order context | All (scoped) | Cancel, view invoice/route/complaints | Orders API | Order + lines + history | M |
| D-05 | New/Edit Customer (Drawer) | Customers | Staff-assisted registration | Manager, Dispatcher, AgencyAdmin | Save | Customers API | Customer fields | M |
| D-06 | Customer List | Customers | Search/browse customers | Manager, Dispatcher, Accountant, AgencyAdmin | Search, open detail | Customers API | Customer list | L |
| D-07 | Customer Detail + Ledger | Customers | Full profile + real-time cylinder balance/history | All (scoped) | Edit, view orders, view ledger history | Customers + Ledger API | Customer + ledger transactions | L |
| D-08 | Route Planning Board | Delivery | Build routes from pending orders | Dispatcher, Manager, AgencyAdmin | Assign orders to route, assign driver/vehicle | Routes + Orders API | Orders, drivers, vehicles | XL |
| D-09 | Live Delivery Tracking | Delivery | Monitor active routes | Dispatcher, Manager, AgencyAdmin | Reassign failed stop | Routes API, real-time channel | Route stop statuses | L |
| D-10 | Vehicle Load Confirmation | Delivery | Record load event | WarehouseStaff, Driver | Confirm load | Inventory API | Cylinder type quantities | S |
| D-11 | Reconciliation Review | Inventory/Delivery | Approve shift reconciliation | WarehouseStaff, AgencyAdmin | Approve, flag variance | Inventory API | Expected vs actual | M |
| D-12 | Stock Overview | Inventory | Real-time balance by location/type/status | WarehouseStaff, Manager, AgencyAdmin | Filter, drill into transaction history | Inventory API | InventoryBalance | L |
| D-13 | GRN Entry | Inventory | Record manual goods receipt | WarehouseStaff | Save | Inventory API | GRN fields | S |
| D-14 | Inventory Adjustment | Inventory | Status change / write-off | WarehouseStaff (create), AgencyAdmin/Manager (approve) | Submit, approve | Inventory API | Adjustment fields | M |
| D-15 | Invoice List | Accounting | Browse/filter invoices | Accountant, AgencyAdmin | Filter, open, print | Accounting API | Invoice list | L |
| D-16 | Invoice Detail / Print Preview | Accounting | Full invoice + print | Accountant, AgencyAdmin, Customer(view own) | Print, record payment, request credit note | Accounting API | Invoice + lines + payments | M |
| D-17 | Payment Recording | Accounting | Record a payment | Accountant, Driver | Save | Accounting API | Payment fields | S |
| D-18 | Credit Note Request/Approval | Accounting | Refund workflow | Accountant (request), Manager/AgencyAdmin (approve) | Submit, approve/reject | Accounting API | Credit note fields | M |
| D-19 | Outstanding Balances Report | Accounting/Reports | Aging view of unpaid invoices | Accountant, AgencyAdmin | Filter, export | Reports API | Aggregated balances | L |
| D-20 | Complaint Queue | Complaints | Triage/manage complaints | Manager, Dispatcher, Accountant (assigned) | Assign, resolve, escalate | Complaints API | Complaint list w/ SLA | L |
| D-21 | Complaint Detail | Complaints | Full complaint context | Assigned staff, Manager | Resolve, escalate, add notes | Complaints API | Complaint + history | M |
| D-22 | Report Catalog | Reports | Browse available reports | All staff (scoped) | Select report | Reports API | Report type list | S |
| D-23 | Report Viewer | Reports | View/filter/export a report | All staff (scoped) | Filter, export | Reports API | Report data | L |
| D-24 | Tenant Configuration | Admin | GST, caps, credit limits, policies | AgencyAdmin | Edit, save | Tenant API | Config key/values | M |
| D-25 | Staff & Roles | Admin | Manage staff accounts | AgencyAdmin | Invite, deactivate, assign role | Identity API | User list | L |
| D-26 | Branches & Warehouses | Admin | Multi-branch management | AgencyAdmin | CRUD | Tenant API | Branch/warehouse list | M |
| D-27 | Reference Data Management | Admin | Cylinder types, complaint categories, tax types | AgencyAdmin | CRUD | Reference Data API | Reference table rows | M |
| D-28 | Notifications Center | Global | View notification history | All staff | Mark read, navigate to source | Notifications API | Notification list | S |
| D-29 | Profile & Settings | Global | Personal preferences, theme | All staff | Edit, save | Identity API | User profile | S |
| D-30 | Print Preview (Generic) | Global | Preview any printable document | Role-dependent | Print, download PDF | Printing model | Print payload | M |

## Customer Mobile App

| # | Screen | Purpose | Primary Actions | Dependencies | Expected Data | Complexity |
|---|---|---|---|---|---|---|
| C-01 | Splash / Phone Entry | Entry point | Enter phone | Auth API | phone number | S |
| C-02 | OTP Verification | Authenticate | Enter OTP | Auth API | OTP code | S |
| C-03 | Profile Setup | Onboarding | Save profile | Customers API | name, type, address | M |
| C-04 | KYC Upload | Optional verification | Upload document | Customers API | file | S |
| C-05 | Home | Central hub | Book refill, view balance | Orders + Ledger API | balance, recent orders | M |
| C-06 | Book Refill | Create order | Select qty, address, payment, submit | Orders API | order fields | M |
| C-07 | Order Tracking | Live status | View status stepper | Orders API, push | order status | M |
| C-08 | Order History | Past orders | Filter, open detail | Orders API | order list | M |
| C-09 | Order Detail (Customer view) | Full order info | Download invoice, raise complaint | Orders + Accounting API | order + invoice | M |
| C-10 | Cylinder Ledger | Balance history | View transactions | Ledger API | balance + history | M |
| C-11 | Payment Method | Pay for an order | Select/enter payment | Payment Gateway | payment fields | M |
| C-12 | Raise Complaint | File a complaint | Select category, describe, submit | Complaints API | complaint fields | M |
| C-13 | Complaint Status | Track complaint | View status, give feedback | Complaints API | complaint + resolution | M |
| C-14 | Addresses | Manage delivery addresses | Add/edit/set primary | Customers API | address list | S |
| C-15 | Notifications | Notification history | View, navigate | Notifications API | notification list | S |
| C-16 | Settings/Profile | Personal settings, language | Edit, save | Customers API | profile fields | S |

## Driver Mobile App

| # | Screen | Purpose | Primary Actions | Dependencies | Expected Data | Complexity |
|---|---|---|---|---|---|---|
| DR-01 | Login (OTP) | Authenticate | Enter phone + OTP | Auth API | phone, OTP | S |
| DR-02 | Today's Route | Daily overview | View stops, start route | Delivery API (offline-cached) | route + stops | L |
| DR-03 | Vehicle Load Confirmation | Confirm load at shift start | Confirm quantities | Inventory API | load lines | S |
| DR-04 | Stop Navigation | Navigate to a stop | Open maps, mark arrived | Route Stop | address, coordinates | S |
| DR-05 | Delivery Confirmation | Record POD | OTP entry, signature, photo, GPS capture | Orders API (offline-queued) | POD fields | L |
| DR-06 | Payment Collection | Collect payment | Select method, enter amount | Accounting API (offline-queued) | payment fields | M |
| DR-07 | Failed Delivery | Record a failed attempt | Select reason, choose resolution | Orders API | reason code | S |
| DR-08 | Route Summary | End-of-route overview | Review completed/failed stops | Route Stop list | stop statuses | M |
| DR-09 | End-of-Shift Reconciliation | Reconcile stock + cash | Enter actuals, submit | Inventory + Accounting API | reconciliation fields | L |
| DR-10 | Sync Status | Offline queue visibility | View pending/synced actions | Local (Drift) | sync queue | S |
| DR-11 | Profile/Settings | Personal settings | Edit, logout | Identity API | profile fields | S |

## Best Practices
- Every screen ID is stable and referenced by `07-wireframe-specifications.md` and `25-lovable-prompts.md` — never renumbered.
- Complexity ratings drive sprint planning honesty — XL screens (Route Planning Board) get dedicated design/dev time, not squeezed into a generic "CRUD screen" estimate.

## Risks
- Screen count (61 across three apps) risks scope creep if not tracked against this inventory — this document is the checklist for "is the design complete," not just a reference.

## Future Scalability
- New Phase 2 screens (WhatsApp booking config, BI dashboards, OMC integration status) will be appended with new IDs continuing each app's numbering sequence, never renumbering existing screens.
