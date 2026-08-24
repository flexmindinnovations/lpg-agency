import type { Route } from '@angular/router';

/** Mounted at `/platform/agencies`, gated by `platformAuthGuard` (the
 * whole `/platform` tree is `super_admin`-only already) plus
 * `tenant:manage_platform`, live-checked server-side. */
export const platformFeatureAgenciesRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./agency-management-page/agency-management-page').then(
        (m) => m.AgencyManagementPage,
      ),
    title: 'Agencies',
  },
];
