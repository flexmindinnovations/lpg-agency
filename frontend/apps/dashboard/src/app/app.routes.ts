import { Route } from '@angular/router';
import { authGuard, permissionGuard } from '@lpg/shared/data-access';
import { ShellLayout } from './shell/shell-layout';

/**
 * Routing foundation.
 *
 * Feature routes are lazy-loaded per feature library, matching the Nx boundary
 * rule (ADR-018) — so a route boundary and a module boundary are the same line.
 *
 * `/login` is a sibling of the shell-wrapped tree, not a child of it
 * (ADR-036) — it must be reachable without an existing session, and without
 * the sidebar/top-bar chrome `ShellLayout` renders. It is declared first so
 * the router matches it before ever trying `ShellLayout`'s own catch-all
 * child route. Every other route sits under `ShellLayout`, gated by
 * `authGuard`.
 */
export const appRoutes: Route[] = [
  {
    path: 'login',
    loadChildren: () => import('@lpg/auth/feature-login').then((m) => m.authFeatureLoginRoutes),
  },
  {
    path: '',
    component: ShellLayout,
    canActivate: [authGuard],
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
        canActivate: [permissionGuard('customers:read')],
        loadChildren: () =>
          import('@lpg/customer/feature-customers').then((m) => m.featureCustomersRoutes),
      },
      {
        path: 'ledger/:customerId',
        canActivate: [permissionGuard('customers:read')],
        loadComponent: () =>
          import('@lpg/ledger/feature-ledger').then((m) => m.FeatureLedger),
      },
      {
        path: 'drivers',
        canActivate: [permissionGuard('drivers:read')],
        loadChildren: () =>
          import('@lpg/delivery/feature-drivers').then((m) => m.deliveryDriversRoutes),
      },
      {
        path: 'vehicles',
        canActivate: [permissionGuard('vehicles:read')],
        loadChildren: () =>
          import('@lpg/delivery/feature-vehicles').then((m) => m.deliveryVehiclesRoutes),
      },
      {
        path: 'dispatch',
        canActivate: [permissionGuard('routes:read')],
        loadChildren: () =>
          import('@lpg/delivery/feature-dispatch').then((m) => m.deliveryDispatchRoutes),
      },
      {
        path: 'inventory',
        canActivate: [permissionGuard('inventory:read')],
        loadChildren: () =>
          import('@lpg/inventory/feature-inventory').then((m) => m.inventoryFeatureRoutes),
      },
      {
        path: 'orders',
        canActivate: [permissionGuard('orders:read')],
        loadChildren: () => import('@lpg/order/feature-orders').then((m) => m.ordersFeatureRoutes),
      },
      {
        path: 'invoices',
        canActivate: [permissionGuard('invoices:read')],
        loadChildren: () => import('@lpg/accounting/feature-invoices').then((m) => m.featureInvoicesRoutes),
      },
      {
        path: 'admin/branches',
        canActivate: [permissionGuard('tenant:configure')],
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then(
            (m) => m.adminFeatureTenantSettingsRoutes,
          ),
      },
      {
        path: 'admin/warehouses',
        canActivate: [permissionGuard('tenant:configure')],
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then((m) => m.adminFeatureWarehousesRoutes),
      },
      {
        path: 'admin/cylinder-types',
        canActivate: [permissionGuard('tenant:configure')],
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then(
            (m) => m.adminFeatureCylinderTypesRoutes,
          ),
      },
      {
        path: 'admin/tenant-config',
        canActivate: [permissionGuard('tenant:configure')],
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then(
            (m) => m.adminFeatureTenantConfigurationRoutes,
          ),
      },
      {
        path: 'admin/price-lists',
        canActivate: [permissionGuard('tenant:configure')],
        loadChildren: () =>
          import('@lpg/admin/feature-tenant-settings').then((m) => m.adminFeaturePriceListRoutes),
      },
      {
        path: 'admin/feature-flags/platform',
        canActivate: [permissionGuard('feature_flags:manage_platform')],
        loadChildren: () =>
          import('@lpg/admin/feature-flags').then((m) => m.adminFeaturePlatformFlagsRoutes),
      },
      {
        path: 'admin/feature-flags',
        canActivate: [permissionGuard('feature_flags:manage_tenant')],
        loadChildren: () =>
          import('@lpg/admin/feature-flags').then((m) => m.adminFeatureFlagsRoutes),
      },
      {
        path: 'admin/users',
        canActivate: [permissionGuard('users:manage')],
        loadChildren: () =>
          import('@lpg/admin/feature-users').then((m) => m.adminFeatureUsersRoutes),
      },
      {
        path: 'admin/audit-log',
        canActivate: [permissionGuard('audit:read')],
        loadChildren: () =>
          import('@lpg/admin/feature-audit-log').then((m) => m.adminFeatureAuditLogRoutes),
      },
      {
        path: 'admin/employees',
        canActivate: [permissionGuard('users:manage')],
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
