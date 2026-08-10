import type { Route } from '@angular/router';

/** Mounted at `/admin/feature-flags`, gated by `feature_flags:manage_tenant`. */
export const adminFeatureFlagsRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./feature-flag-overrides-page/feature-flag-overrides-page').then(
        (m) => m.FeatureFlagOverridesPage,
      ),
    title: 'Feature Flag Overrides',
  },
];

/** Mounted at `/admin/feature-flags/platform`, gated by `feature_flags:manage_platform`. */
export const adminFeaturePlatformFlagsRoutes: Route[] = [
  {
    path: '',
    loadComponent: () =>
      import('./platform-flags-page/platform-flags-page').then((m) => m.PlatformFlagsPage),
    title: 'Platform Feature Flags',
  },
];
