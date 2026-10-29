import { Route } from '@angular/router';
import {
  authGuard,
  licenseGuard,
  permissionGuard,
  platformAuthGuard,
} from '@lpg/shared/data-access';

/** `driver` holds `customers:read`/`drivers:read`/`vehicles:read`/`routes:read`
 * only for narrow, single-record API calls tied to their own delivery
 * workflow (see `permission.guard.ts`'s `excludeRoles` doc) — not to browse
 * these full staff-facing list/planning pages. */
const STAFF_LIST_EXCLUDED_ROLES = ['driver'] as const;

/**
 * Routing foundation.
 *
 * Feature routes are lazy-loaded per feature library, matching the Nx boundary
 * rule (ADR-018) — so a route boundary and a module boundary are the same line.
 *
 * `/login`, `/license-required`, and `/platform` are siblings of the
 * tenant-shell-wrapped tree, not children of it (ADR-036 for `/login`, same
 * reasoning applies to the license gate and the Platform Console — a
 * `super_admin` session has no tenant to render `ShellLayout`'s nav around).
 * They are declared first so the router matches them before ever trying
 * `ShellLayout`'s own catch-all child route. Every tenant-scoped route sits
 * under `ShellLayout`, gated by `authGuard` then `licenseGuard` (auth must
 * resolve first — `licenseGuard` needs a resolved principal); `/platform`
 * is gated by `authGuard` then `platformAuthGuard` instead, with no license
 * gate at all (`platform-shell.ts`'s own docstring).
 */
export const appRoutes: Route[] = [
  {
    path: 'login',
    loadChildren: () => import('@lpg/auth/feature-login').then((m) => m.authFeatureLoginRoutes),
  },
  // The links the backend emails: `/reset-password?token=…` (forgot password)
  // and `/set-password?token=…` (invitation / new agency). The page is loaded
  // directly rather than redirected so the `token` query param is never lost.
  {
    path: 'reset-password',
    loadComponent: () => import('@lpg/auth/feature-login').then((m) => m.ResetPasswordPage),
    title: 'Choose a new password',
    data: { mode: 'reset' },
  },
  {
    path: 'set-password',
    loadComponent: () => import('@lpg/auth/feature-login').then((m) => m.ResetPasswordPage),
    title: 'Set your password',
    data: { mode: 'setup' },
  },
  {
    path: 'license-required',
    loadComponent: () =>
      import('./license-required/license-required').then((m) => m.LicenseRequired),
    title: 'License Required',
  },
  {
    path: 'platform',
    loadComponent: () => import('./platform-shell/platform-shell').then((m) => m.PlatformShell),
    canActivate: [authGuard, platformAuthGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'agencies' },
      {
        path: 'agencies',
        canActivate: [permissionGuard('tenant:manage_platform')],
        loadChildren: () =>
          import('@lpg/platform/feature-agencies').then((m) => m.platformFeatureAgenciesRoutes),
      },
      {
        path: 'licenses',
        canActivate: [permissionGuard('license:manage_platform')],
        loadChildren: () =>
          import('@lpg/admin/feature-license').then((m) => m.adminFeatureLicenseIssuanceRoutes),
      },
      {
        path: 'feature-flags',
        canActivate: [permissionGuard('feature_flags:manage_platform')],
        loadChildren: () =>
          import('@lpg/admin/feature-flags').then((m) => m.adminFeaturePlatformFlagsRoutes),
      },
    ],
  },
  {
    path: '',
    loadComponent: () => import('./shell/shell-layout').then((m) => m.ShellLayout),
    canActivate: [authGuard, licenseGuard],
    children: [
      {
        path: '',
        loadComponent: () => import('./home/home').then((m) => m.Home),
        title: 'LPG Agency Management Platform',
      },
      {
        // One home for personal and agency-wide settings. The shell
        // only supplies the frame and section nav; every section is still its
        // own lazy route with its own permission guard, so a section the user
        // cannot open is hidden from the nav and refused by the router.
        path: 'settings',
        loadComponent: () => import('./settings/settings-shell').then((m) => m.SettingsShell),
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'account' },
          {
            path: 'account',
            loadComponent: () => import('./profile/profile').then((m) => m.Profile),
            title: 'My Profile',
            data: {
              breadcrumbs: [
                { label: 'Settings' },
                { label: 'My Profile', routerLink: '/settings/account' },
              ],
            },
          },
          {
            path: 'agency',
            canActivate: [permissionGuard('tenant:read')],
            loadComponent: () =>
              import('./settings/agency/agency-settings').then((m) => m.AgencySettings),
            title: 'Agency',
            data: {
              breadcrumbs: [
                { label: 'Settings' },
                { label: 'Agency', routerLink: '/settings/agency' },
              ],
            },
          },
          {
            path: 'configuration',
            canActivate: [permissionGuard('tenant:configure')],
            data: {
              breadcrumbs: [
                { label: 'Settings' },
                { label: 'Configuration', routerLink: '/settings/configuration' },
              ],
            },
            loadChildren: () =>
              import('@lpg/admin/feature-tenant-settings').then(
                (m) => m.adminFeatureTenantConfigurationRoutes,
              ),
          },
          {
            path: 'payments',
            canActivate: [permissionGuard('tenant:configure')],
            loadComponent: () =>
              import('./settings/payments/payment-settings').then((m) => m.PaymentSettings),
            title: 'Payments',
            data: {
              breadcrumbs: [
                { label: 'Settings' },
                { label: 'Payments', routerLink: '/settings/payments' },
              ],
            },
          },
          {
            path: 'configuration/tdt-rating',
            canActivate: [permissionGuard('tenant:configure')],
            data: {
              breadcrumbs: [
                { label: 'Settings' },
                { label: 'Configuration', routerLink: '/settings/configuration' },
                { label: 'TDT Rating', routerLink: '/settings/configuration/tdt-rating' },
              ],
            },
            loadChildren: () =>
              import('@lpg/compliance/feature-tdt-rating').then((m) => m.complianceTdtRatingRoutes),
          },
          {
            path: 'feature-flags',
            canActivate: [permissionGuard('feature_flags:manage_tenant')],
            data: {
              breadcrumbs: [
                { label: 'Settings' },
                { label: 'Feature Flags', routerLink: '/settings/feature-flags' },
              ],
            },
            loadChildren: () =>
              import('@lpg/admin/feature-flags').then((m) => m.adminFeatureFlagsRoutes),
          },
          {
            path: 'license/devices',
            canActivate: [permissionGuard('license:manage_tenant')],
            data: {
              breadcrumbs: [
                { label: 'Settings' },
                { label: 'Linked Devices', routerLink: '/settings/license/devices' },
              ],
            },
            loadChildren: () =>
              import('@lpg/admin/feature-license').then((m) => m.adminFeatureLicenseDevicesRoutes),
          },
          {
            path: 'license',
            canActivate: [permissionGuard('license:manage_tenant')],
            data: {
              breadcrumbs: [
                { label: 'Settings' },
                { label: 'License', routerLink: '/settings/license' },
              ],
            },
            loadChildren: () =>
              import('@lpg/admin/feature-license').then((m) => m.adminFeatureLicenseRoutes),
          },
        ],
      },
      // Pre-Settings URLs — kept so bookmarks and links already shared keep working.
      { path: 'profile', pathMatch: 'full', redirectTo: 'settings/account' },
      {
        path: 'admin/tenant-config/tdt-rating',
        pathMatch: 'full',
        redirectTo: 'settings/configuration/tdt-rating',
      },
      { path: 'admin/tenant-config', pathMatch: 'full', redirectTo: 'settings/configuration' },
      { path: 'admin/feature-flags', pathMatch: 'full', redirectTo: 'settings/feature-flags' },
      {
        path: 'admin/license/devices',
        pathMatch: 'full',
        redirectTo: 'settings/license/devices',
      },
      { path: 'admin/license', pathMatch: 'full', redirectTo: 'settings/license' },
      {
        // Internal design-system reference (Phase 29). No permission gate —
        // it shows components and tokens, no tenant data. Reached from the
        // profile menu, not the primary nav.
        path: 'design-system',
        loadComponent: () =>
          import('./design-system/design-system.page').then((m) => m.DesignSystemPage),
        title: 'Design System',
        data: { breadcrumbs: [{ label: 'Design System' }] },
      },
      // Phase 7 (Administration) — each admin area is its own route,
      // gated by the exact permission code its endpoints require
      // server-side (`docs/data/17-api-security.md` §6). The client-side
      // check is a UI convenience only; the API re-enforces every one of
      // these regardless (`permission.guard.ts`'s own docstring).
      {
        path: 'customers',
        canActivate: [permissionGuard('customers:read', STAFF_LIST_EXCLUDED_ROLES)],
        data: { breadcrumbs: [{ label: 'Customers', routerLink: '/customers' }] },
        loadChildren: () =>
          import('@lpg/customer/feature-customers').then((m) => m.featureCustomersRoutes),
      },
      {
        path: 'ledger/:customerId',
        // The ledger endpoint needs ledger:read (DO-22); guarding on
        // customers:read let some roles open a page that always 403'd.
        canActivate: [permissionGuard('ledger:read', STAFF_LIST_EXCLUDED_ROLES)],
        data: {
          breadcrumbs: [
            { label: 'Customers', routerLink: '/customers' },
            { label: 'Customer Ledger' },
          ],
        },
        loadComponent: () => import('@lpg/ledger/feature-ledger').then((m) => m.FeatureLedger),
      },
      {
        path: 'drivers',
        canActivate: [permissionGuard('drivers:read', STAFF_LIST_EXCLUDED_ROLES)],
        data: { breadcrumbs: [{ label: 'Drivers', routerLink: '/drivers' }] },
        loadChildren: () =>
          import('@lpg/delivery/feature-drivers').then((m) => m.deliveryDriversRoutes),
      },
      {
        path: 'vehicles',
        canActivate: [permissionGuard('vehicles:read', STAFF_LIST_EXCLUDED_ROLES)],
        data: { breadcrumbs: [{ label: 'Fleet Vehicles', routerLink: '/vehicles' }] },
        loadChildren: () =>
          import('@lpg/delivery/feature-vehicles').then((m) => m.deliveryVehiclesRoutes),
      },
      {
        path: 'dispatch',
        canActivate: [permissionGuard('routes:read', STAFF_LIST_EXCLUDED_ROLES)],
        data: { breadcrumbs: [{ label: 'Dispatch', routerLink: '/dispatch' }] },
        loadChildren: () =>
          import('@lpg/delivery/feature-dispatch').then((m) => m.deliveryDispatchRoutes),
      },
      {
        path: 'scales',
        canActivate: [permissionGuard('weighment:record', STAFF_LIST_EXCLUDED_ROLES)],
        data: { breadcrumbs: [{ label: 'Scales', routerLink: '/scales' }] },
        loadChildren: () =>
          import('@lpg/compliance/feature-scales').then((m) => m.complianceScalesRoutes),
      },
      {
        path: 'cylinder-units',
        canActivate: [permissionGuard('cylinder_units:read', STAFF_LIST_EXCLUDED_ROLES)],
        data: { breadcrumbs: [{ label: 'Cylinder Units', routerLink: '/cylinder-units' }] },
        loadChildren: () =>
          import('@lpg/compliance/feature-cylinder-units').then(
            (m) => m.complianceCylinderUnitsRoutes,
          ),
      },
      {
        path: 'compliance-calendar',
        canActivate: [permissionGuard('compliance:read', STAFF_LIST_EXCLUDED_ROLES)],
        data: {
          breadcrumbs: [{ label: 'Compliance Calendar', routerLink: '/compliance-calendar' }],
        },
        loadChildren: () =>
          import('@lpg/compliance/feature-compliance-calendar').then(
            (m) => m.complianceComplianceCalendarRoutes,
          ),
      },
      {
        path: 'inventory',
        canActivate: [permissionGuard('inventory:read')],
        data: { breadcrumbs: [{ label: 'Inventory', routerLink: '/inventory' }] },
        loadChildren: () =>
          import('@lpg/inventory/feature-inventory').then((m) => m.inventoryFeatureRoutes),
      },
      {
        path: 'orders',
        canActivate: [permissionGuard('orders:read')],
        data: { breadcrumbs: [{ label: 'Orders', routerLink: '/orders' }] },
        loadChildren: () => import('@lpg/order/feature-orders').then((m) => m.ordersFeatureRoutes),
      },
      {
        path: 'invoices',
        canActivate: [permissionGuard('invoices:read')],
        data: { breadcrumbs: [{ label: 'Invoices', routerLink: '/invoices' }] },
        loadChildren: () =>
          import('@lpg/accounting/feature-invoices').then((m) => m.featureInvoicesRoutes),
      },
      {
        path: 'cash-handovers',
        canActivate: [permissionGuard('cash_handovers:review')],
        data: { breadcrumbs: [{ label: 'Cash Handovers', routerLink: '/cash-handovers' }] },
        loadChildren: () =>
          import('@lpg/accounting/feature-invoices').then((m) => m.cashHandoverRegisterRoutes),
      },
      {
        path: 'complaints',
        canActivate: [permissionGuard('complaints.manage')],
        data: { breadcrumbs: [{ label: 'Complaints', routerLink: '/complaints' }] },
        loadChildren: () =>
          import('@lpg/complaint/feature-complaints').then((m) => m.featureComplaintsRoutes),
      },
      {
        path: 'reports',
        canActivate: [permissionGuard('reports:read')],
        data: { breadcrumbs: [{ label: 'Reports', routerLink: '/reports' }] },
        loadChildren: () =>
          import('@lpg/reporting/feature-reports').then((m) => m.reportingFeatureReportsRoutes),
      },
      {
        path: 'ai-assistant',
        canActivate: [permissionGuard('ai:read')],
        data: { breadcrumbs: [] },
        loadChildren: () =>
          import('@lpg/ai/feature-ai-assistant').then((m) => m.aiFeatureAiAssistantRoutes),
      },
      {
        path: 'admin/branches',
        canActivate: [permissionGuard('tenant:configure')],
        data: {
          breadcrumbs: [{ label: 'Admin' }, { label: 'Branches', routerLink: '/admin/branches' }],
        },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then(
            (m) => m.adminFeatureTenantSettingsRoutes,
          ),
      },
      {
        path: 'admin/warehouses',
        canActivate: [permissionGuard('tenant:configure')],
        data: {
          breadcrumbs: [{ label: 'Admin' }, { label: 'Godowns', routerLink: '/admin/warehouses' }],
        },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then((m) => m.adminFeatureWarehousesRoutes),
      },
      {
        path: 'admin/cylinder-types',
        canActivate: [permissionGuard('tenant:configure')],
        data: {
          breadcrumbs: [
            { label: 'Admin' },
            { label: 'Cylinder Types', routerLink: '/admin/cylinder-types' },
          ],
        },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then(
            (m) => m.adminFeatureCylinderTypesRoutes,
          ),
      },
      {
        path: 'admin/price-lists',
        canActivate: [permissionGuard('tenant:configure')],
        data: {
          breadcrumbs: [
            { label: 'Admin' },
            { label: 'Price Lists', routerLink: '/admin/price-lists' },
          ],
        },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then((m) => m.adminFeaturePriceListRoutes),
      },
      {
        path: 'admin/users',
        canActivate: [permissionGuard('users:manage')],
        data: {
          breadcrumbs: [{ label: 'Admin' }, { label: 'Staff Users', routerLink: '/admin/users' }],
        },
        loadChildren: () =>
          import('@lpg/admin/feature-users').then((m) => m.adminFeatureUsersRoutes),
      },
      {
        path: 'admin/audit-log',
        canActivate: [permissionGuard('audit:read')],
        data: {
          breadcrumbs: [{ label: 'Admin' }, { label: 'Audit Log', routerLink: '/admin/audit-log' }],
        },
        loadChildren: () =>
          import('@lpg/admin/feature-audit-log').then((m) => m.adminFeatureAuditLogRoutes),
      },
      {
        path: 'admin/employees',
        canActivate: [permissionGuard('users:manage')],
        data: {
          breadcrumbs: [{ label: 'Admin' }, { label: 'Employees', routerLink: '/admin/employees' }],
        },
        loadChildren: () =>
          import('@lpg/tenant-admin/feature-employees').then(
            (m) => m.tenantAdminFeatureEmployeesRoutes,
          ),
      },
      {
        path: 'notifications',
        data: { breadcrumbs: [{ label: 'Notifications', routerLink: '/notifications' }] },
        loadChildren: () =>
          import('@lpg/notification/feature-notifications').then(
            (m) => m.notificationFeatureNotificationsRoutes,
          ),
      },
      {
        // Where `permissionGuard` sends a signed-in user whose role lacks
        // the page's permission (DO-31) — an explicit state, not a silent
        // bounce to Home.
        path: 'no-access',
        loadComponent: () => import('./not-found/not-found').then((m) => m.NotFound),
        data: { variant: 'no-access' },
        title: 'No access',
      },
      {
        path: '**',
        loadComponent: () => import('./not-found/not-found').then((m) => m.NotFound),
        title: 'Page not found',
      },
    ],
  },
];
