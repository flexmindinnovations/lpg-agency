import type { Route } from '@angular/router';

/** Mounted at `/admin/license`, gated by `license:manage_tenant`. */
export const adminFeatureLicenseRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./license-activation-page/license-activation-page').then(
        (m) => m.LicenseActivationPage,
      ),
    title: 'License',
  },
];

/** Mounted at `/admin/license/devices`, gated by `license:manage_tenant`. */
export const adminFeatureLicenseDevicesRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./linked-devices-page/linked-devices-page').then((m) => m.LinkedDevicesPage),
    title: 'Linked Devices',
  },
];

/** Mounted at `/admin/license/issuance`, gated by `license:manage_platform`. */
export const adminFeatureLicenseIssuanceRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./license-issuance-page/license-issuance-page').then(
        (m) => m.LicenseIssuancePage,
      ),
    title: 'License Issuance',
  },
];
