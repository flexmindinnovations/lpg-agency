# Customer App V2 (Professional Features) Plan

## Objective
Evolve the existing Flutter Customer App from a basic single-screen dashboard into a professional, multi-feature mobile application. 

## Scope
Introduce a persistent Bottom Navigation Bar architecture using `StatefulShellRoute` in `go_router`, dividing the app into 4 primary domains:
1. **Dashboard:** Overview and quick actions.
2. **Orders:** Active and past orders.
3. **Support:** Help center and complaint management.
4. **Profile:** User settings and master data.

## Features

### 1. Push Notifications & Inbox
- Add a notifications bell icon to the Dashboard App Bar.
- Create an inbox screen (`notifications_screen.dart`) to display order status updates and promotional messages.

### 2. Payments & Invoicing
- **Payment Methods:** Manage saved cards and UPI inside the Profile tab.
- **Invoicing:** Provide functionality to view and download order receipts from past orders inside the Orders tab.

### 3. Address Management
- Introduce an Address Management screen inside the Profile tab.
- Allow users to view saved delivery locations and initiate a mock "Add New Address" flow.

### 4. Live Order Tracking
- Introduce an Active Order Details screen (`order_tracking_screen.dart`).
- Display a map placeholder tracking the delivery vehicle.
- Display a timeline of order milestones (Placed -> Out for Delivery -> Delivered).

### 5. Support & KYC
- **Support:** A dedicated Help Center tab to raise complaints (gas leaks, delays) and view ticket history.
- **KYC Details:** View official connection details (SV number, cylinder limits) in the Profile tab.

## Technical Approach
- Use `StatefulShellRoute` for the main navigation shell.
- Continue using the dark, minimalist, monochromatic design system established in Phase 5/6.
- **Backend Integration:** Integrate directly with the existing Phase 8 (Customers), Phase 14 (Invoicing), Phase 15 (Notifications), and Phase 17 (Complaints) REST APIs using the `api_client` package. We will replace the originally proposed mock data with live backend connections, except for Payment Gateways which remain a UI placeholder.
