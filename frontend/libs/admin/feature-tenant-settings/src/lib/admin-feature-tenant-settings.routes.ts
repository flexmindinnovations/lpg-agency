import type { Route } from '@angular/router';

/**
 * Mounted under `/admin/*` in `apps/dashboard/src/app/app.routes.ts`, each
 * segment gated by its own `permissionGuard('tenant:configure')` at the
 * parent route — see that file for the exact wiring.
 */
export const adminFeatureTenantSettingsRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./branches-page/branches-page').then((m) => m.BranchesPage),
    title: 'Branches',
  },
];

export const adminFeatureWarehousesRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./warehouses-page/warehouses-page').then((m) => m.WarehousesPage),
    title: 'Warehouses',
  },
];

export const adminFeatureCylinderTypesRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./cylinder-types-page/cylinder-types-page').then((m) => m.CylinderTypesPage),
    title: 'Cylinder Types',
  },
];

export const adminFeatureTenantConfigurationRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./tenant-configuration-page/tenant-configuration-page').then(
        (m) => m.TenantConfigurationPage,
      ),
    title: 'Tenant Configuration',
  },
];

export const adminFeaturePriceListRoutes: Route[] = [
  {
    path: '',
    loadComponent: () => import('./price-list-page/price-list-page').then((m) => m.PriceListPage),
    title: 'Price List',
  },
];
