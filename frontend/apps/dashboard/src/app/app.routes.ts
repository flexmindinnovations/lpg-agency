import { Route } from '@angular/router';
import { authGuard, licenseGuard, permissionGuard, platformAuthGuard } from '@lpg/shared/data-access';

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
        path: 'profile',
        loadComponent: () => import('./profile/profile').then((m) => m.Profile),
        title: 'My Profile',
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
        canActivate: [permissionGuard('customers:read', STAFF_LIST_EXCLUDED_ROLES)],
        data: { breadcrumbs: [{ label: 'Customers', routerLink: '/customers' }, { label: 'Customer Ledger' }] },
        loadComponent: () =>
          import('@lpg/ledger/feature-ledger').then((m) => m.FeatureLedger),
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
        loadChildren: () => import('@lpg/accounting/feature-invoices').then((m) => m.featureInvoicesRoutes),
      },
      {
        path: 'complaints',
        canActivate: [permissionGuard('complaints.manage')],
        data: { breadcrumbs: [{ label: 'Complaints', routerLink: '/complaints' }] },
        loadChildren: () => import('@lpg/complaint/feature-complaints').then((m) => m.featureComplaintsRoutes),
      },
      {
        path: 'reports',
        canActivate: [permissionGuard('reports:read')],
        data: { breadcrumbs: [{ label: 'Reports', routerLink: '/reports' }] },
        loadChildren: () => import('@lpg/reporting/feature-reports').then((m) => m.reportingFeatureReportsRoutes),
      },
      {
        path: 'admin/branches',
        canActivate: [permissionGuard('tenant:configure')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Branches', routerLink: '/admin/branches' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then(
            (m) => m.adminFeatureTenantSettingsRoutes,
          ),
      },
      {
        path: 'admin/warehouses',
        canActivate: [permissionGuard('tenant:configure')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Warehouses', routerLink: '/admin/warehouses' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then((m) => m.adminFeatureWarehousesRoutes),
      },
      {
        path: 'admin/cylinder-types',
        canActivate: [permissionGuard('tenant:configure')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Cylinder Types', routerLink: '/admin/cylinder-types' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then(
            (m) => m.adminFeatureCylinderTypesRoutes,
          ),
      },
      {
        path: 'admin/tenant-config',
        canActivate: [permissionGuard('tenant:configure')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Tenant Config', routerLink: '/admin/tenant-config' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then(
            (m) => m.adminFeatureTenantConfigurationRoutes,
          ),
      },
      {
        path: 'admin/price-lists',
        canActivate: [permissionGuard('tenant:configure')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Price Lists', routerLink: '/admin/price-lists' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then((m) => m.adminFeaturePriceListRoutes),
      },
      {
        path: 'admin/feature-flags',
        canActivate: [permissionGuard('feature_flags:manage_tenant')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Feature Flags', routerLink: '/admin/feature-flags' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-flags').then((m) => m.adminFeatureFlagsRoutes),
      },
      {
        path: 'admin/license/devices',
        canActivate: [permissionGuard('license:manage_tenant')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Linked Devices', routerLink: '/admin/license/devices' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-license').then((m) => m.adminFeatureLicenseDevicesRoutes),
      },
      {
        path: 'admin/license',
        canActivate: [permissionGuard('license:manage_tenant')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'License', routerLink: '/admin/license' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-license').then((m) => m.adminFeatureLicenseRoutes),
      },
      {
        path: 'admin/users',
        canActivate: [permissionGuard('users:manage')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Staff Users', routerLink: '/admin/users' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-users').then((m) => m.adminFeatureUsersRoutes),
      },
      {
        path: 'admin/audit-log',
        canActivate: [permissionGuard('audit:read')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Audit Log', routerLink: '/admin/audit-log' }] },
        loadChildren: () =>
          import('@lpg/admin/feature-audit-log').then((m) => m.adminFeatureAuditLogRoutes),
      },
      {
        path: 'admin/employees',
        canActivate: [permissionGuard('users:manage')],
        data: { breadcrumbs: [{ label: 'Admin' }, { label: 'Employees', routerLink: '/admin/employees' }] },
        loadChildren: () =>
          import('@lpg/tenant-admin/feature-employees').then((m) => m.tenantAdminFeatureEmployeesRoutes),
      },
      {
        path: 'notifications',
        loadChildren: () =>
          import('@lpg/notification/feature-notifications').then(
            (m) => m.notificationFeatureNotificationsRoutes,
          ),
      },
      {
        path: '**',
        loadComponent: () => import('./not-found/not-found').then((m) => m.NotFound),
        title: 'Page not found',
      },
    ],
  },
];
